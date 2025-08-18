"""
Ultra Simple File Converter Dependencies
Only what's needed for handover compatibility
"""
from dataclasses import dataclass
from typing import Optional

@dataclass
class FileConverterDependencies:
    """Minimal dependencies for handover compatibility"""
    session_id: Optional[str] = None
    requester_agent: Optional[str] = None
    task_id: Optional[str] = None
    
    @classmethod
    def create_default(
        cls,
        session_id: Optional[str] = None,
        requester_agent: Optional[str] = None,
        task_id: Optional[str] = None,
        **kwargs
    ):
        return cls(
            session_id=session_id,
            requester_agent=requester_agent,
            task_id=task_id
        )