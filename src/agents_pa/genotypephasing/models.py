"""
Pydantic models for Genotype Phasing Agent.
Defines output models and parameter classes for structured agent interactions.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class FileReadyStatus(BaseModel):
    """Model for determining user's file readiness status"""
    status: str = Field(
        ..., 
        description="User's readiness status: 'ready', 'not_ready', or 'other_types'"
    )


class GenotypePhasingResult(BaseModel):
    """Model for genotype phasing execution results"""
    success: bool = Field(..., description="Whether phasing was successful")
    output_files: List[str] = Field(default_factory=list, description="List of generated output files")
    message: str = Field(..., description="Result message for user")
    error: Optional[str] = Field(None, description="Error message if failed")


class GenotypePhasingState(BaseModel):
    """Model for tracking agent state"""
    stage: str = Field(default="welcome", description="Current workflow stage")
    myoutputfile: List[str] = Field(default_factory=list, description="List of output files")
    session_id: Optional[str] = Field(None, description="Session identifier")
    current_session_id: Optional[str] = Field(None, description="Current active session identifier")
    
    def reset(self):
        """Reset state to initial values"""
        self.stage = "welcome"
        self.myoutputfile = []
        # Don't reset current_session_id here as it's used for session tracking