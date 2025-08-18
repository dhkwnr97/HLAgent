"""
Dependencies and context management for Genotype Phasing Agent.
Handles session state, external integrations, and dependency injection.
"""

import os
from dataclasses import dataclass
from typing import Optional, List
from dotenv import load_dotenv

from .models import GenotypePhasingState
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)


@dataclass
class GenotypePhasingDependencies:
    """Dependencies for genotype phasing agent execution"""
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
    ) -> "GenotypePhasingDependencies":
        """Create default dependencies with environment setup"""
        return cls(
            session_id=session_id,
            requester_agent=requester_agent,
            task_id=task_id
        )


class GenotypePhasingSession:
    """Session management for genotype phasing agent"""
    
    def __init__(self, deps: GenotypePhasingDependencies):
        self.deps = deps
        self.state = GenotypePhasingState()
        logger.info(f"Initialized genotype phasing session: {deps.session_id}")
    
    def get_phasing_config_path(self) -> str:
        """Get path to phasing configuration file"""
        return os.path.join(
            self.deps.hlagent_main_dir,
            "src/tools/HATK/Runners/phasing_run_config_orig.yaml"
        )
    
    def get_phasing_script_path(self) -> str:
        """Get path to phasing execution script"""
        return os.path.join(
            self.deps.hlagent_main_dir,
            "src/tools/HATK/Runners/run_phasing.py"
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