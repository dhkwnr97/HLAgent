"""
Pydantic models for HLA Imputation Agent.
Defines output models and parameter classes for structured agent interactions.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict


class FileReadyStatus(BaseModel):
    """Model for determining user's file readiness status"""
    status: str = Field(
        ..., 
        description="User's readiness status: 'ready', 'not_ready', or 'other_types'"
    )


class HLAImputationResult(BaseModel):
    """Model for HLA imputation execution results"""
    success: bool = Field(..., description="Whether imputation was successful")
    tool_used: str = Field(..., description="HLA imputation tool that was used")
    output_files: List[str] = Field(default_factory=list, description="List of generated output files")
    message: str = Field(..., description="Result message for user")
    error: Optional[str] = Field(None, description="Error message if failed")


class HLAImputationState(BaseModel):
    """Model for tracking agent state"""
    stage: str = Field(default="welcome", description="Current workflow stage")
    myoutputfile: List[str] = Field(default_factory=list, description="List of output files")
    available_tools: List[str] = Field(default_factory=list, description="List of available HLA tools")
    selected_tool: Optional[str] = Field(None, description="Currently selected HLA tool")
    current_session_id: Optional[str] = Field(None, description="Current active session identifier")
    
    def reset(self):
        """Reset state to initial values"""
        self.stage = "welcome"
        self.myoutputfile = []
        self.selected_tool = None
        # Don't reset current_session_id and available_tools as they're used for session tracking


class HLAToolInfo(BaseModel):
    """Model for HLA tool information"""
    name: str = Field(..., description="Tool name")
    supported: bool = Field(..., description="Whether the tool is supported")
    required_files: List[str] = Field(..., description="Required file formats for this tool")
    description: str = Field(..., description="Tool description")


class ToolSelectionResult(BaseModel):
    """Model for tool selection validation"""
    valid: bool = Field(..., description="Whether the selection is valid")
    tool_name: str = Field(..., description="Resolved tool name")
    error_message: Optional[str] = Field(None, description="Error message if invalid")