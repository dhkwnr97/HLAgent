"""
Pydantic models for Parameter Handler Agent.
Defines structured outputs and request/response models.
"""

from typing import List, Dict, Any, Optional, Union
from pydantic import BaseModel, Field
from enum import Enum


class YamlEditRequest(BaseModel):
    """Model for YAML edit requests."""
    line_number: int = Field(..., description="Line number to modify (1-indexed)")
    new_value: Union[str, int, float, bool, List[Any]] = Field(..., description="New value for the line")
    
    class Config:
        json_schema_extra = {
            "examples": [
                {"line_number": 19, "new_value": 18},
                {"line_number": 47, "new_value": ["A", "B", "C"]},
                {"line_number": 58, "new_value": False}
            ]
        }


class YamlModificationResult(BaseModel):
    """Model for YAML modification results."""
    success: bool = Field(..., description="Whether the modification was successful")
    line_number: int = Field(..., description="Line number that was modified")
    old_value: str = Field(..., description="Original value")
    new_value: str = Field(..., description="New value")
    message: str = Field(..., description="Result message")


class SessionState(BaseModel):
    """Model for agent session state."""
    original_yaml_path: str = Field(..., description="Path to original YAML file")
    working_yaml_path: str = Field(..., description="Path to working YAML file")
    session_id: str = Field(..., description="Session identifier")
    requester_agent: Optional[str] = Field(default=None, description="Requesting agent name")
    task_id: Optional[str] = Field(default=None, description="Task identifier")
    awaiting_confirmation: bool = Field(default=False, description="Whether awaiting user confirmation")
    task_complete: bool = Field(default=False, description="Whether task is complete")
    modifications_made: List[YamlModificationResult] = Field(default_factory=list, description="List of modifications made")


class AgentResponse(BaseModel):
    """Model for agent responses."""
    message: str = Field(..., description="Response message")
    requires_input: bool = Field(..., description="Whether agent requires user input")
    session_complete: bool = Field(default=False, description="Whether session is complete")
    success: bool = Field(default=True, description="Whether operation was successful")
    data: Optional[Dict[str, Any]] = Field(default=None, description="Additional response data")


class YamlFileInfo(BaseModel):
    """Model for YAML file information."""
    path: str = Field(..., description="File path")
    line_count: int = Field(..., description="Number of lines in file")
    content_preview: str = Field(..., description="Preview of file content")
    last_modified: Optional[str] = Field(default=None, description="Last modification time")