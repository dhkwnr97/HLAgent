"""
HLA Fine Mapping Agent - Dependencies
Context dependencies and external service integrations for workflow execution.
"""
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any
from dotenv import load_dotenv

from src.utils.logger import setup_logger

logger = setup_logger(__name__)
load_dotenv()


@dataclass
class HLAFineMappingDependencies:
    """Dependencies for HLA Fine Mapping Agent execution"""
    session_id: str
    requester_agent: str = "supervisor"
    task_id: Optional[str] = None
    
    # Environment paths
    hlagent_main_directory: str = None
    output_directory: str = None
    
    # Configuration
    max_execution_time: int = 3600  # 1 hour timeout for node execution
    
    # Context tracking
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        """Initialize paths and validate environment"""
        if self.hlagent_main_directory is None:
            self.hlagent_main_directory = os.getenv("HLAGENT_MAIN_DIRECTORY")
            if not self.hlagent_main_directory:
                raise ValueError("HLAGENT_MAIN_DIRECTORY not found in environment")
        
        if self.output_directory is None:
            self.output_directory = os.path.join(self.hlagent_main_directory, "data/output")
        
        if self.metadata is None:
            self.metadata = {}
        
        # Validate critical paths exist
        if not os.path.exists(self.hlagent_main_directory):
            raise ValueError(f"Main directory does not exist: {self.hlagent_main_directory}")
        
        # Ensure output directory exists
        os.makedirs(self.output_directory, exist_ok=True)
        
        logger.info(f"HLAFineMappingDependencies initialized for session: {self.session_id}")
    
    @classmethod
    def create_default(
        cls,
        session_id: str,
        requester_agent: str = "supervisor",
        task_id: Optional[str] = None
    ) -> "HLAFineMappingDependencies":
        """Create default dependencies with environment-based configuration"""
        return cls(
            session_id=session_id,
            requester_agent=requester_agent,
            task_id=task_id or f"hlafinemapping_{session_id}"
        )
    
    def get_tool_config_path(self, tool_name: str) -> str:
        """Get path to HATK tool configuration file"""
        return os.path.join(
            self.hlagent_main_directory,
            "src/tools/HATK/Runners",
            f"{tool_name}_run_config_orig.yaml"
        )
    
    def get_tool_script_path(self, tool_name: str) -> str:
        """Get path to HATK tool script"""
        return os.path.join(
            self.hlagent_main_directory,
            "src/tools/HATK/Runners",
            f"run_{tool_name}.py"
        )
    
    def get_node_output_directory(self, node_name: str) -> str:
        """Get output directory for specific node"""
        node_output_dir = os.path.join(self.output_directory, "HLAFineMapping", node_name)
        os.makedirs(node_output_dir, exist_ok=True)
        return node_output_dir
    
    def log_execution_context(self, context: str):
        """Log execution context for debugging"""
        logger.info(f"[{self.session_id}] {context}")
        self.metadata[f"context_{len(self.metadata)}"] = {
            "timestamp": str(os.times()),
            "context": context
        }
    
    def validate_required_files(self, file_paths: list) -> bool:
        """Validate that required files exist"""
        for file_path in file_paths:
            if not os.path.exists(file_path):
                logger.error(f"Required file not found: {file_path}")
                return False
        return True
    
    def get_example_phenotype_file(self) -> str:
        """Get path to example phenotype file"""
        return os.path.join(
            self.hlagent_main_directory,
            "data/examples/wtccc_filtered_58C_RA.hatk.300+300.phe"
        )