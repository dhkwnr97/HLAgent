"""
HLA Fine Mapping Agent - Pydantic Models
Defines data models for workflow configuration, state management, and output handling.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from enum import Enum


class WorkflowStage(str, Enum):
    """Workflow stages for HLA Fine Mapping Agent"""
    WELCOME = "welcome"
    WORKFLOW_CUSTOMIZE = "workflow_customize"
    WORKFLOW_CONFIRM = "workflow_confirm"
    EXECUTING_NODES = "executing_nodes"
    FINISHED = "finished"


class NodeType(str, Enum):
    """Available node types for HLA Fine Mapping"""
    NODE1 = "node1"  # HLA binary marker panel creation
    NODE2 = "node2"  # Regression analysis
    NODE3 = "node3"  # Stepwise conditional regression
    NODE4 = "node4"  # Omnibus test
    NODE5 = "node5"  # Meta analysis


class WorkflowConfiguration(BaseModel):
    """Configuration for workflow execution order"""
    nodes: List[NodeType] = Field(default=[], description="List of nodes to execute in order")
    current_node_index: int = Field(default=0, description="Index of currently executing node")
    
    def get_current_node(self) -> Optional[NodeType]:
        """Get the currently executing node"""
        if 0 <= self.current_node_index < len(self.nodes):
            return self.nodes[self.current_node_index]
        return None
    
    def advance_to_next_node(self) -> bool:
        """Advance to next node, returns True if more nodes available"""
        self.current_node_index += 1
        return self.current_node_index < len(self.nodes)
    
    def is_complete(self) -> bool:
        """Check if all nodes have been executed"""
        return self.current_node_index >= len(self.nodes)


class WorkflowParseRequest(BaseModel):
    """Request model for parsing natural language workflow instructions"""
    user_input: str = Field(..., description="Natural language workflow description")


class WorkflowParseResponse(BaseModel):
    """Response model for parsed workflow configuration"""
    nodes: List[NodeType] = Field(..., description="Parsed node execution order")
    description: str = Field(..., description="Human-readable description of the workflow")


class NodeExecutionState(BaseModel):
    """State tracking for individual node execution"""
    node_type: NodeType
    status: Literal["pending", "in_progress", "completed", "failed"] = "pending"
    output_files: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None


class HLAFineMappingState(BaseModel):
    """Complete state model for HLA Fine Mapping Agent"""
    stage: WorkflowStage = WorkflowStage.WELCOME
    workflow_config: WorkflowConfiguration = Field(default_factory=WorkflowConfiguration)
    myoutputfile: List[str] = Field(default_factory=list, description="All output files from workflow")
    node_states: List[NodeExecutionState] = Field(default_factory=list)
    session_id: Optional[str] = None
    current_session_id: Optional[str] = None
    
    def reset(self):
        """Reset state to initial welcome stage"""
        self.stage = WorkflowStage.WELCOME
        self.workflow_config = WorkflowConfiguration()
        self.myoutputfile = []
        self.node_states = []
    
    def add_output_files(self, files: List[str]):
        """Add files to the global output file list"""
        self.myoutputfile.extend(files)
    
    def get_node_state(self, node_type: NodeType) -> Optional[NodeExecutionState]:
        """Get execution state for a specific node"""
        for state in self.node_states:
            if state.node_type == node_type:
                return state
        return None
    
    def update_node_state(self, node_type: NodeType, status: str, output_files: List[str] = None, error_message: str = None):
        """Update execution state for a specific node"""
        for state in self.node_states:
            if state.node_type == node_type:
                state.status = status
                if output_files:
                    state.output_files.extend(output_files)
                if error_message:
                    state.error_message = error_message
                return
        
        # Create new state if not found
        new_state = NodeExecutionState(
            node_type=node_type,
            status=status,
            output_files=output_files or [],
            error_message=error_message
        )
        self.node_states.append(new_state)


class FileRequirement(BaseModel):
    """Model for file requirements in node execution"""
    file_types: List[str] = Field(..., description="Required file extensions")
    description: str = Field(..., description="Human-readable description of requirements")
    example_files: List[str] = Field(default_factory=list, description="Example file paths")


class NodeInfo(BaseModel):
    """Information about a specific node"""
    node_type: NodeType
    name: str
    description: str
    requirements: FileRequirement
    output_suffixes: List[str]
    output_prefixes: List[str] = Field(default_factory=list)