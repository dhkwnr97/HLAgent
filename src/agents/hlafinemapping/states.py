"""
State management for HLA Fine Mapping Agent.

Manages session state, workflow progress, and agent state transitions.
"""

import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field

from .agent_types import (
    HLAFineMappingState, NodeType, WorkflowExecutionState, AgentSession,
    WorkflowConfiguration, NodeResult, WorkflowMetrics, OutputFileInfo,
    WorkflowPauseInfo, ReadinessState, ContinueDecision
)
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


@dataclass
class HLAgentState:
    """Core state for the HLA Fine Mapping Agent."""
    session_id: str = ""
    requester_agent: str = ""
    task_id: str = ""
    is_standalone: bool = True
    current_state: HLAFineMappingState = HLAFineMappingState.IDLE
    
    # Workflow configuration
    workflow_config: Optional[WorkflowConfiguration] = None
    selected_nodes: List[str] = field(default_factory=list)
    workflow_sequence: List[str] = field(default_factory=list)
    current_node_index: int = 0
    current_node: Optional[str] = None
    
    # File management
    output_files: List[str] = field(default_factory=list)
    output_file_info: List[OutputFileInfo] = field(default_factory=list)
    
    # Execution tracking
    node_results: Dict[str, NodeResult] = field(default_factory=dict)
    workflow_metrics: Optional[WorkflowMetrics] = None
    
    # Session management
    start_time: Optional[datetime] = None
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    
    # Pause/Resume handling
    is_paused: bool = False
    pause_info: Optional[WorkflowPauseInfo] = None
    
    # Error handling
    error_message: Optional[str] = None
    has_error: bool = False
    
    # User readiness
    user_readiness: ReadinessState = ReadinessState.UNKNOWN
    continue_decision: ContinueDecision = ContinueDecision.UNKNOWN


class HLAFineMappingStateManager:
    """State manager for the HLA Fine Mapping Agent."""
    
    def __init__(self):
        self.state = HLAFineMappingState.IDLE
        self.state_history: List[HLAFineMappingState] = []
        self.transition_callbacks: Dict[HLAFineMappingState, List[Callable]] = {}
    
    def initialize_session(self, requester_agent: str = "", task_id: str = "") -> str:
        """
        Initialize a new session.
        
        Args:
            requester_agent: Name of the requesting agent (empty for standalone)
            task_id: Task identifier
            
        Returns:
            Session ID
        """
        session_id = str(uuid.uuid4())
        
        self.state = HLAgentState(
            session_id=session_id,
            requester_agent=requester_agent,
            task_id=task_id,
            is_standalone=not bool(requester_agent),
            start_time=datetime.now(),
            current_state=HLAFineMappingState.IDLE
        )
        
        # Initialize output files list
        self.state.output_files = []
        
        logger.info(f"Initialized new session: {session_id}")
        logger.info(f"Standalone mode: {self.state.is_standalone}")
        
        return session_id
    
    def transition(self, new_state: HLAFineMappingState, context: Dict[str, Any] = None) -> bool:
        """
        Transition to a new state.
        
        Args:
            new_state: Target state
            context: Optional context information
            
        Returns:
            True if transition was successful
        """
        old_state = self.state.current_state
        
        # Validate transition
        if not self._is_valid_transition(old_state, new_state):
            logger.warning(f"Invalid state transition: {old_state} -> {new_state}")
            return False
        
        # Update state
        self.state_history.append(old_state)
        self.state.current_state = new_state
        
        # Execute transition callbacks
        if new_state in self.transition_callbacks:
            for callback in self.transition_callbacks[new_state]:
                try:
                    callback(old_state, new_state, context)
                except Exception as e:
                    logger.error(f"Error in transition callback: {e}")
        
        logger.info(f"State transition: {old_state} -> {new_state}")
        return True
    
    def _is_valid_transition(self, from_state: HLAFineMappingState, to_state: HLAFineMappingState) -> bool:
        """
        Validate if a state transition is allowed.
        
        Args:
            from_state: Current state
            to_state: Target state
            
        Returns:
            True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            HLAFineMappingState.IDLE: [HLAFineMappingState.WAITING_USER_READY, HLAFineMappingState.ERROR],
            HLAFineMappingState.WAITING_USER_READY: [HLAFineMappingState.READY_CHECK, HLAFineMappingState.ERROR],
            HLAFineMappingState.READY_CHECK: [HLAFineMappingState.NODE_EXPLANATION, HLAFineMappingState.COMPLETED, HLAFineMappingState.ERROR],
            HLAFineMappingState.NODE_EXPLANATION: [HLAFineMappingState.WORKFLOW_CUSTOMIZATION, HLAFineMappingState.ERROR],
            HLAFineMappingState.WORKFLOW_CUSTOMIZATION: [HLAFineMappingState.WORKFLOW_EXECUTION, HLAFineMappingState.ERROR],
            HLAFineMappingState.WORKFLOW_EXECUTION: [HLAFineMappingState.WORKFLOW_COMPLETE, HLAFineMappingState.ERROR],
            HLAFineMappingState.WORKFLOW_COMPLETE: [HLAFineMappingState.CONTINUE_PROMPT, HLAFineMappingState.ERROR],
            HLAFineMappingState.CONTINUE_PROMPT: [HLAFineMappingState.NODE_EXPLANATION, HLAFineMappingState.COMPLETED, HLAFineMappingState.ERROR],
            HLAFineMappingState.COMPLETED: [],
            HLAFineMappingState.ERROR: [HLAFineMappingState.IDLE, HLAFineMappingState.COMPLETED]
        }
        
        return to_state in valid_transitions.get(from_state, [])
    
    def set_workflow_configuration(self, selected_nodes: List[str], workflow_sequence: List[str]) -> bool:
        """
        Set the workflow configuration.
        
        Args:
            selected_nodes: List of selected node names
            workflow_sequence: Sequence of nodes to execute
            
        Returns:
            True if configuration was set successfully
        """
        try:
            # Validate nodes
            valid_nodes = [node.value for node in NodeType]
            invalid_nodes = [node for node in selected_nodes if node not in valid_nodes]
            
            if invalid_nodes:
                self.state.error_message = f"Invalid nodes: {invalid_nodes}"
                return False
            
            # Create workflow configuration
            self.state.workflow_config = WorkflowConfiguration(
                selected_nodes=selected_nodes,
                workflow_sequence=workflow_sequence,
                description=f"Workflow with nodes: {', '.join(workflow_sequence)}"
            )
            
            self.state.selected_nodes = selected_nodes
            self.state.workflow_sequence = workflow_sequence
            self.state.current_node_index = 0
            
            logger.info(f"Workflow configuration set: {workflow_sequence}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting workflow configuration: {e}")
            self.state.error_message = str(e)
            return False
    
    def add_output_file(self, file_path: str, generated_by_node: str = "", description: str = "") -> bool:
        """
        Add an output file to the tracking list.
        
        Args:
            file_path: Path to the output file
            generated_by_node: Node that generated the file
            description: Optional description
            
        Returns:
            True if file was added successfully
        """
        try:
            if file_path not in self.state.output_files:
                self.state.output_files.append(file_path)
                
                # Create file info if possible
                try:
                    import os
                    if os.path.exists(file_path):
                        file_info = OutputFileInfo(
                            file_path=file_path,
                            file_type=os.path.splitext(file_path)[1],
                            generated_by_node=generated_by_node,
                            size_bytes=os.path.getsize(file_path),
                            creation_time=datetime.now(),
                            description=description
                        )
                        self.state.output_file_info.append(file_info)
                except Exception as e:
                    logger.warning(f"Could not create file info for {file_path}: {e}")
                
                logger.info(f"Added output file: {file_path}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error adding output file: {e}")
            return False
    
    def clear_output_files(self) -> None:
        """Clear all output files."""
        self.state.output_files.clear()
        self.state.output_file_info.clear()
        logger.info("Cleared output files")
    
    def set_node_result(self, node_name: str, result: NodeResult) -> None:
        """
        Set the result for a node.
        
        Args:
            node_name: Name of the node
            result: Node execution result
        """
        self.state.node_results[node_name] = result
        logger.info(f"Set result for node {node_name}: {result.status}")
    
    def get_current_node(self) -> Optional[str]:
        """
        Get the current node being executed.
        
        Returns:
            Current node name or None
        """
        if (self.state.current_node_index < len(self.state.workflow_sequence) and
            self.state.current_node_index >= 0):
            return self.state.workflow_sequence[self.state.current_node_index]
        return None
    
    def advance_to_next_node(self) -> bool:
        """
        Advance to the next node in the workflow.
        
        Returns:
            True if there is a next node, False if workflow is complete
        """
        self.state.current_node_index += 1
        
        if self.state.current_node_index < len(self.state.workflow_sequence):
            self.state.current_node = self.state.workflow_sequence[self.state.current_node_index]
            return True
        else:
            self.state.current_node = None
            return False
    
    def is_workflow_complete(self) -> bool:
        """
        Check if the workflow is complete.
        
        Returns:
            True if workflow is complete
        """
        return (self.state.current_node_index >= len(self.state.workflow_sequence) and
                len(self.state.workflow_sequence) > 0)
    
    def set_pause_info(self, pause_info: WorkflowPauseInfo) -> None:
        """
        Set workflow pause information.
        
        Args:
            pause_info: Pause information
        """
        self.state.is_paused = True
        self.state.pause_info = pause_info
        logger.info(f"Workflow paused: {pause_info.reason}")
    
    def clear_pause_info(self) -> None:
        """Clear workflow pause information."""
        self.state.is_paused = False
        self.state.pause_info = None
        logger.info("Workflow pause cleared")
    
    def set_error(self, error_message: str) -> None:
        """
        Set error state.
        
        Args:
            error_message: Error message
        """
        self.state.has_error = True
        self.state.error_message = error_message
        self.transition(HLAFineMappingState.ERROR)
        logger.error(f"Agent error: {error_message}")
    
    def clear_error(self) -> None:
        """Clear error state."""
        self.state.has_error = False
        self.state.error_message = None
        logger.info("Error state cleared")
    
    def add_conversation(self, role: str, content: str) -> None:
        """
        Add a conversation entry.
        
        Args:
            role: Role (user/assistant)
            content: Content of the message
        """
        self.state.conversation_history.append({
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat()
        })
    
    def get_workflow_status(self) -> Dict[str, Any]:
        """
        Get comprehensive workflow status.
        
        Returns:
            Dictionary with workflow status information
        """
        completed_nodes = list(self.state.node_results.keys())
        total_nodes = len(self.state.workflow_sequence)
        
        return {
            "session_id": self.state.session_id,
            "current_state": self.state.current_state.value,
            "is_standalone": self.state.is_standalone,
            "workflow_progress": {
                "total_nodes": total_nodes,
                "completed_nodes": len(completed_nodes),
                "current_node": self.get_current_node(),
                "remaining_nodes": total_nodes - len(completed_nodes),
                "progress_percentage": (len(completed_nodes) / total_nodes * 100) if total_nodes > 0 else 0
            },
            "output_files": {
                "total_files": len(self.state.output_files),
                "file_paths": self.state.output_files
            },
            "execution_info": {
                "start_time": self.state.start_time.isoformat() if self.state.start_time else None,
                "is_paused": self.state.is_paused,
                "has_error": self.state.has_error,
                "error_message": self.state.error_message
            },
            "conversation_count": len(self.state.conversation_history)
        }
    
    def get_session_info(self) -> Dict[str, Any]:
        """
        Get session information for supervisor integration.
        
        Returns:
            Session information dictionary
        """
        return {
            "session_id": self.state.session_id,
            "requester_agent": self.state.requester_agent,
            "task_id": self.state.task_id,
            "is_standalone": self.state.is_standalone,
            "current_state": self.state.current_state.value,
            "workflow_status": self.get_workflow_status()
        }
    
    def is_session_complete(self) -> bool:
        """
        Check if the session is complete.
        
        Returns:
            True if session is complete
        """
        return self.state.current_state == HLAFineMappingState.COMPLETED
    
    def register_transition_callback(self, state: HLAFineMappingState, callback: Callable) -> None:
        """
        Register a callback for state transitions.
        
        Args:
            state: State to register callback for
            callback: Callback function
        """
        if state not in self.transition_callbacks:
            self.transition_callbacks[state] = []
        self.transition_callbacks[state].append(callback)