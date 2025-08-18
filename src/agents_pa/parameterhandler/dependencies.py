"""
Dependencies for Parameter Handler Agent using PydanticAI.
Manages external service integrations and agent context.
"""

from dataclasses import dataclass
from typing import Optional
from pathlib import Path


@dataclass
class ParameterHandlerDependencies:
    """Dependencies for Parameter Handler Agent execution."""
    
    session_id: str
    requester_agent: Optional[str] = None
    task_id: Optional[str] = None
    original_yaml_path: Optional[str] = None
    working_yaml_path: Optional[str] = None
    
    @classmethod
    def create_default(
        cls, 
        session_id: str,
        requester_agent: str = "standalone",
        task_id: str = "",
        original_yaml_path: str = ""
    ) -> "ParameterHandlerDependencies":
        """Create default dependencies for parameter handler."""
        return cls(
            session_id=session_id,
            requester_agent=requester_agent,
            task_id=task_id,
            original_yaml_path=original_yaml_path,
            working_yaml_path=None
        )
    
    def set_yaml_paths(self, original_path: str, working_path: str) -> None:
        """Set YAML file paths."""
        self.original_yaml_path = original_path
        self.working_yaml_path = working_path
    
    def get_working_yaml_path(self) -> str:
        """Get working YAML file path, creating from original if needed."""
        if self.working_yaml_path:
            return self.working_yaml_path
        
        if self.original_yaml_path:
            # Convert _orig.yaml to .yaml
            original_path = Path(self.original_yaml_path)
            if original_path.name.endswith('_orig.yaml'):
                working_name = original_path.name.replace('_orig.yaml', '.yaml')
                self.working_yaml_path = str(original_path.parent / working_name)
                return self.working_yaml_path
        
        return ""
    
    def is_standalone(self) -> bool:
        """Check if running in standalone mode."""
        return self.requester_agent == "standalone" or not self.requester_agent