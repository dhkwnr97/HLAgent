"""
Dependencies and context management for HLA Imputation Agent.
Handles session state, external integrations, and dependency injection.
"""

import os
from dataclasses import dataclass
from typing import Optional, List
from dotenv import load_dotenv

from .models import HLAImputationState
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)


@dataclass
class HLAImputationDependencies:
    """Dependencies for HLA imputation agent execution"""
    session_id: str
    requester_agent: str = "supervisor"
    task_id: Optional[str] = None
    hlagent_main_dir: str = None
    
    def __post_init__(self):
        if self.hlagent_main_dir is None:
            self.hlagent_main_dir = os.getenv("HLAGENT_MAIN_DIRECTORY")
    
    @classmethod
    def create_default(
        cls,
        session_id: str,
        requester_agent: str = "supervisor",
        task_id: Optional[str] = None
    ) -> "HLAImputationDependencies":
        """Create default dependencies with environment setup"""
        return cls(
            session_id=session_id,
            requester_agent=requester_agent,
            task_id=task_id
        )


class HLAImputationSession:
    """Session management for HLA imputation agent"""
    
    def __init__(self, deps: HLAImputationDependencies):
        self.deps = deps
        self.state = HLAImputationState()
        logger.info(f"Initialized HLA imputation session: {deps.session_id}")
    
    def get_hla_tools_directory(self) -> str:
        """Get path to HLA imputation tools directory"""
        return os.path.join(
            self.deps.hlagent_main_dir,
            "src/tools/HLAimputation"
        )
    
    def get_tool_config_path(self, tool_name: str) -> str:
        """Get path to tool configuration file"""
        return os.path.join(
            self.deps.hlagent_main_dir,
            f"src/tools/HLAimputation/{tool_name}/{tool_name}_run_config_orig.yaml"
        )
    
    def get_tool_script_path(self, tool_name: str) -> str:
        """Get path to tool execution script"""
        return os.path.join(
            self.deps.hlagent_main_dir,
            f"src/tools/HLAimputation/{tool_name}/{tool_name}_run.py"
        )
    
    def add_output_files(self, files: List[str]):
        """Add output files to session state"""
        self.state.myoutputfile.extend(files)
        logger.info(f"Added {len(files)} output files to session")
    
    def reset_session(self):
        """Reset session state"""
        self.state.reset()
        logger.info(f"Reset session state for: {self.deps.session_id}")
    
    def get_output_files(self) -> List[str]:
        """Get list of all output files"""
        return self.state.myoutputfile.copy()
    
    def set_available_tools(self, tools: List[str]):
        """Set the list of available tools"""
        self.state.available_tools = tools
        logger.info(f"Set available tools: {tools}")
    
    def set_selected_tool(self, tool: str):
        """Set the selected tool"""
        self.state.selected_tool = tool
        logger.info(f"Selected tool: {tool}")