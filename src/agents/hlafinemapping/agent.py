"""
HLA Fine Mapping Agent.

A professional HLA fine mapping agent with customizable workflows.
Supports standalone operation and supervisor integration with advanced
node-based workflow customization.
"""

import os
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from src.core.llm_config import get_llm
from langchain_core.messages import SystemMessage, HumanMessage

from .agent_types import (
    HLAFineMappingState, NodeType, AgentResponse, ResponseType, 
    ReadinessState, ContinueDecision, NodeResult, WorkflowConfiguration
)
from .states import HLAFineMappingStateManager
from .tools import (
    validate_user_readiness, validate_continue_decision, parse_node_selection,
    validate_required_files, get_node_description, get_node_requirements,
    format_output_files_list, create_workflow_execution_plan,
    estimate_workflow_duration, validate_output_directory,
    generate_workflow_summary, get_workflow_recommendations
)
from .prompts import (
    SYSTEM_PROMPT, WELCOME_MESSAGE, SUPERVISOR_WELCOME_MESSAGE,
    FILE_REQUIREMENTS_MESSAGE, NOT_READY_MESSAGE, NODE_EXPLANATION_MESSAGE,
    WORKFLOW_CONSTRUCTION_MESSAGE, WORKFLOW_EXECUTION_START, NODE_EXECUTION_START,
    NODE_EXECUTION_COMPLETE, WORKFLOW_COMPLETE_MESSAGE, CONTINUE_PROMPT_MESSAGE,
    AGENT_FINISHED_MESSAGE, ERROR_INVALID_NODES, ERROR_WORKFLOW_EXECUTION,
    HELP_MESSAGE, NODE1_START_MESSAGE, NODE2_START_MESSAGE, NODE3_START_MESSAGE,
    NODE4_START_MESSAGE, NODE4_PHASING_MESSAGE, NODE5_START_MESSAGE
)
from src.core.workchain import create_workchain
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


class HLAFineMappingAgent:
    """
    HLA Fine Mapping Agent with customizable workflows.
    
    Features:
    - Interactive chatting loop with users
    - Customizable workflow with 5 nodes
    - Workchain integration for parameter handling
    - Supervisor agent integration
    - Output file tracking and management
    - Comprehensive error handling and validation
    """
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.llm = get_llm()
        self.state_manager = HLAFineMappingStateManager()
        self._supervisor_handoff_callback = supervisor_handoff_callback
        self.output_files: List[str] = []
        
        # Initialize nodes
        self.nodes = self._initialize_nodes()
    
    @property
    def supervisor_handoff_callback(self) -> Optional[Callable]:
        """Get supervisor handoff callback."""
        return self._supervisor_handoff_callback
    
    @supervisor_handoff_callback.setter
    def supervisor_handoff_callback(self, callback: Optional[Callable]):
        """Set supervisor handoff callback and update all nodes."""
        self._supervisor_handoff_callback = callback
        # Update callback in all existing nodes
        for node in self.nodes.values():
            if hasattr(node, 'supervisor_handoff_callback'):
                node.supervisor_handoff_callback = callback
        
    def _initialize_nodes(self) -> Dict[str, Any]:
        """Initialize all node instances."""
        try:
            from .Nodes.node1 import Node1
            from .Nodes.node2 import Node2
            from .Nodes.node3 import Node3
            from .Nodes.node4 import Node4
            from .Nodes.node5 import Node5
            
            return {
                "node1": Node1(self._supervisor_handoff_callback),
                "node2": Node2(self._supervisor_handoff_callback),
                "node3": Node3(self._supervisor_handoff_callback),
                "node4": Node4(self._supervisor_handoff_callback),
                "node5": Node5(self._supervisor_handoff_callback)
            }
        except ImportError as e:
            logger.error(f"Error importing nodes: {e}")
            return {}
    
    async def chat_loop(self, requester_agent: str = "", task_id: str = "") -> Dict[str, Any]:
        """
        Main interactive chat loop for the agent.
        
        Args:
            requester_agent: Name of the requesting agent (empty for standalone)
            task_id: Task identifier
            
        Returns:
            Final session result
        """
        try:
            # Initialize session
            session_id = self.state_manager.initialize_session(requester_agent, task_id)
            
            # Display welcome message
            if self.state_manager.state.is_standalone:
                print(WELCOME_MESSAGE)
            else:
                print(SUPERVISOR_WELCOME_MESSAGE.format(requester=requester_agent))
            
            # Initialize output files
            self.output_files = []
            self.state_manager.clear_output_files()
            
            # Start main interaction loop
            while not self.state_manager.is_session_complete():
                try:
                    # Get user input
                    user_input = input("To HLA Fine Mapping Agent: ").strip()
                    
                    # Handle exit commands
                    if user_input.lower() in ["Done!", "exit", "quit", "abort"]:
                        print("Session aborted by user.")
                        break
                    
                    # Process user input
                    response = await self._process_user_input(user_input)
                    
                    # Display response
                    print(f"\n{response.message}")
                    
                    # Check if session is complete
                    if response.session_complete:
                        break
                        
                except KeyboardInterrupt:
                    print("\n\nSession interrupted by user.")
                    break
                except Exception as e:
                    logger.error(f"Error in chat loop: {e}")
                    print(f"Error: {e}\n")
            
            # Generate final session result
            return self._generate_session_result()
            
        except Exception as e:
            logger.error(f"Error in chat loop: {e}")
            return {"status": "error", "message": str(e)}
    
    async def _process_user_input(self, user_input: str) -> AgentResponse:
        """
        Process user input based on current state.
        
        Args:
            user_input: User's input string
            
        Returns:
            AgentResponse with processing result
        """
        try:
            current_state = self.state_manager.state.current_state
            
            # Add to conversation history
            self.state_manager.add_conversation("user", user_input)
            
            # Route based on current state
            if current_state == HLAFineMappingState.IDLE:
                return await self._handle_idle_state(user_input)
            elif current_state == HLAFineMappingState.WAITING_USER_READY:
                return await self._handle_waiting_user_ready(user_input)
            elif current_state == HLAFineMappingState.READY_CHECK:
                return await self._handle_ready_check(user_input)
            elif current_state == HLAFineMappingState.NODE_EXPLANATION:
                return await self._handle_node_explanation(user_input)
            elif current_state == HLAFineMappingState.WORKFLOW_CUSTOMIZATION:
                return await self._handle_workflow_customization(user_input)
            elif current_state == HLAFineMappingState.WORKFLOW_EXECUTION:
                return await self._handle_workflow_execution(user_input)
            elif current_state == HLAFineMappingState.CONTINUE_PROMPT:
                return await self._handle_continue_prompt(user_input)
            else:
                return AgentResponse(
                    response_type=ResponseType.ERROR,
                    message=f"Unknown state: {current_state}",
                    current_state=current_state
                )
                
        except Exception as e:
            logger.error(f"Error processing user input: {e}")
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=f"Error processing input: {str(e)}",
                current_state=self.state_manager.state.current_state
            )
    
    async def _handle_idle_state(self, user_input: str) -> AgentResponse:
        """Handle input when agent is in IDLE state."""
        # Transition to waiting for user readiness
        self.state_manager.transition(HLAFineMappingState.WAITING_USER_READY)
        
        # Display file requirements
        response = AgentResponse(
            response_type=ResponseType.REQUEST_INPUT,
            message=FILE_REQUIREMENTS_MESSAGE,
            current_state=HLAFineMappingState.WAITING_USER_READY,
            requires_input=True
        )
        
        self.state_manager.add_conversation("assistant", response.message)
        return response
    
    async def _handle_waiting_user_ready(self, user_input: str) -> AgentResponse:
        """Handle user readiness response."""
        readiness = validate_user_readiness(user_input)
        
        if readiness == ReadinessState.READY:
            # User is ready, transition to ready check
            self.state_manager.state.user_readiness = ReadinessState.READY
            self.state_manager.transition(HLAFineMappingState.READY_CHECK)
            
            # Move to node explanation
            self.state_manager.transition(HLAFineMappingState.NODE_EXPLANATION)
            
            response = AgentResponse(
                response_type=ResponseType.INFO,
                message=NODE_EXPLANATION_MESSAGE,
                current_state=HLAFineMappingState.NODE_EXPLANATION,
                requires_input=True
            )
            
        elif readiness == ReadinessState.NOT_READY:
            # User is not ready, provide guidance and finish
            self.state_manager.transition(HLAFineMappingState.COMPLETED)
            
            response = AgentResponse(
                response_type=ResponseType.COMPLETION,
                message=NOT_READY_MESSAGE,
                current_state=HLAFineMappingState.COMPLETED,
                session_complete=True
            )
            
        else:
            # Invalid response, ask again
            response = AgentResponse(
                response_type=ResponseType.REQUEST_INPUT,
                message=f"Please respond with 'ready' or 'not ready'.\n\n{FILE_REQUIREMENTS_MESSAGE}",
                current_state=HLAFineMappingState.WAITING_USER_READY,
                requires_input=True
            )
        
        self.state_manager.add_conversation("assistant", response.message)
        return response
    
    async def _handle_ready_check(self, user_input: str) -> AgentResponse:
        """Handle ready check state."""
        # This state is typically skipped, but handle if needed
        self.state_manager.transition(HLAFineMappingState.NODE_EXPLANATION)
        return await self._handle_node_explanation(user_input)
    
    async def _handle_node_explanation(self, user_input: str) -> AgentResponse:
        """Handle node explanation and workflow customization."""
        # Check if user wants to finish (Done! command)
        if user_input.lower() in ["done!", "exit", "quit", "abort"]:
            self.state_manager.transition(HLAFineMappingState.COMPLETED)
            completion_message = self._generate_completion_message()
            
            response = AgentResponse(
                response_type=ResponseType.COMPLETION,
                message=completion_message,
                current_state=HLAFineMappingState.COMPLETED,
                session_complete=True,
                output_files=self.output_files
            )
            self.state_manager.add_conversation("assistant", response.message)
            return response
        
        # Check if user is asking for help
        if user_input.lower() in ["help", "?", "commands"]:
            response = AgentResponse(
                response_type=ResponseType.INFO,
                message=HELP_MESSAGE,
                current_state=HLAFineMappingState.NODE_EXPLANATION,
                requires_input=True
            )
            self.state_manager.add_conversation("assistant", response.message)
            return response
        
        # Parse node selection
        validation_result = parse_node_selection(user_input)
        
        if not validation_result.is_valid:
            # Invalid node selection
            error_message = ERROR_INVALID_NODES.format(
                invalid_nodes=", ".join(validation_result.invalid_nodes)
            )
            if validation_result.missing_dependencies:
                error_message += f"\n\nMissing dependencies: {', '.join(validation_result.missing_dependencies)}"
            
            response = AgentResponse(
                response_type=ResponseType.ERROR,
                message=error_message + f"\n\n{NODE_EXPLANATION_MESSAGE}",
                current_state=HLAFineMappingState.NODE_EXPLANATION,
                requires_input=True
            )
            
        else:
            # Valid node selection, set up workflow
            self.state_manager.set_workflow_configuration(
                validation_result.selected_nodes,
                validation_result.workflow_sequence
            )
            
            # Create execution plan
            execution_plan = create_workflow_execution_plan(validation_result.workflow_sequence)
            duration = estimate_workflow_duration(validation_result.workflow_sequence)
            recommendations = get_workflow_recommendations(validation_result.selected_nodes)
            
            construction_message = WORKFLOW_CONSTRUCTION_MESSAGE.format(
                workflow_sequence=" → ".join(validation_result.workflow_sequence),
                execution_plan=execution_plan,
                total_steps=len(validation_result.workflow_sequence)
            )
            
            # Transition to workflow execution
            self.state_manager.transition(HLAFineMappingState.WORKFLOW_EXECUTION)
            
            response = AgentResponse(
                response_type=ResponseType.WORKFLOW_STATUS,
                message=construction_message,
                current_state=HLAFineMappingState.WORKFLOW_EXECUTION,
                requires_input=False
            )
            
            # Add construction message to conversation (but don't print to avoid duplication)
            self.state_manager.add_conversation("assistant", response.message)
            
            # Start workflow execution
            await self._start_workflow_execution()
        
        return response
    
    async def _handle_workflow_customization(self, user_input: str) -> AgentResponse:
        """Handle workflow customization state."""
        # This is typically handled in node explanation
        return await self._handle_node_explanation(user_input)
    
    async def _handle_workflow_execution(self, user_input: str) -> AgentResponse:
        """Handle workflow execution state."""
        # Workflow execution is automatic, but this handles any interruptions
        response = AgentResponse(
            response_type=ResponseType.INFO,
            message="Workflow is currently executing. Please wait for completion...",
            current_state=HLAFineMappingState.WORKFLOW_EXECUTION,
            requires_input=False
        )
        
        self.state_manager.add_conversation("assistant", response.message)
        return response
    
    async def _handle_continue_prompt(self, user_input: str) -> AgentResponse:
        """Handle continue prompt state."""
        continue_decision = validate_continue_decision(user_input)
        
        if continue_decision == ContinueDecision.CONTINUE:
            # User wants to continue with another workflow
            self.state_manager.transition(HLAFineMappingState.NODE_EXPLANATION)
            
            response = AgentResponse(
                response_type=ResponseType.INFO,
                message=f"Starting new workflow configuration...\n\n{NODE_EXPLANATION_MESSAGE}",
                current_state=HLAFineMappingState.NODE_EXPLANATION,
                requires_input=True
            )
            
        elif continue_decision == ContinueDecision.DONE:
            # User is done, finish agent
            self.state_manager.transition(HLAFineMappingState.COMPLETED)
            
            # Generate completion message
            completion_message = self._generate_completion_message()
            
            response = AgentResponse(
                response_type=ResponseType.COMPLETION,
                message=completion_message,
                current_state=HLAFineMappingState.COMPLETED,
                session_complete=True,
                output_files=self.output_files
            )
            
        else:
            # Invalid response, ask again
            response = AgentResponse(
                response_type=ResponseType.REQUEST_INPUT,
                message=f"Please respond with 'continue' or 'Done!'.\n\n{CONTINUE_PROMPT_MESSAGE}",
                current_state=HLAFineMappingState.CONTINUE_PROMPT,
                requires_input=True
            )
        
        self.state_manager.add_conversation("assistant", response.message)
        return response
    
    async def _start_workflow_execution(self) -> None:
        """Start the workflow execution process."""
        try:
            workflow_sequence = self.state_manager.state.workflow_sequence
            
            print(f"\n{WORKFLOW_EXECUTION_START.format(workflow_sequence=' → '.join(workflow_sequence), total_nodes=len(workflow_sequence))}")
            
            # Execute each node in sequence
            for i, node_name in enumerate(workflow_sequence):
                try:
                    # Update current node
                    self.state_manager.state.current_node_index = i
                    self.state_manager.state.current_node = node_name
                    
                    # Get node description and requirements
                    node_description = get_node_description(node_name)
                    node_requirements = get_node_requirements(node_name)
                    
                    # Display node start message
                    start_message = NODE_EXECUTION_START.format(
                        node_name=node_name.upper(),
                        node_description=node_description,
                        node_specific_message=self._get_node_specific_message(node_name)
                    )
                    print(f"\n{start_message}")
                    
                    # Execute the node
                    node_result = await self._execute_node(node_name)
                    
                    # Store result
                    self.state_manager.set_node_result(node_name, node_result)
                    
                    # Add output files
                    self.output_files.extend(node_result.output_files)
                    for file_path in node_result.output_files:
                        self.state_manager.add_output_file(file_path, node_name)
                    
                    # Display completion message
                    completion_message = NODE_EXECUTION_COMPLETE.format(
                        node_name=node_name.upper(),
                        output_files=format_output_files_list(node_result.output_files),
                        next_action="Moving to next node..." if i < len(workflow_sequence) - 1 else "Workflow complete!"
                    )
                    print(f"\n{completion_message}")
                    
                    if node_result.status == "error":
                        print(f"\n❌ Error in {node_name}: {node_result.error_message}")
                        break
                    
                except Exception as e:
                    logger.error(f"Error executing node {node_name}: {e}")
                    print(f"\n❌ Error executing {node_name}: {e}")
                    break
            
            # Workflow execution complete
            await self._complete_workflow_execution()
            
        except Exception as e:
            logger.error(f"Error in workflow execution: {e}")
            print(f"\n❌ Workflow execution error: {e}")
            self.state_manager.set_error(str(e))
    
    async def _execute_node(self, node_name: str) -> NodeResult:
        """
        Execute a specific node.
        
        Args:
            node_name: Name of the node to execute
            
        Returns:
            NodeResult with execution results
        """
        try:
            start_time = datetime.now()
            
            if node_name in self.nodes:
                node_instance = self.nodes[node_name]
                result = await node_instance.execute(self.state_manager.state)
                
                execution_time = (datetime.now() - start_time).total_seconds()
                
                return NodeResult(
                    node_name=node_name,
                    status=result.get("status", "completed"),
                    output_files=result.get("output_files", []),
                    error_message=result.get("error_message"),
                    execution_time=execution_time
                )
            else:
                return NodeResult(
                    node_name=node_name,
                    status="error",
                    output_files=[],
                    error_message=f"Node {node_name} not found"
                )
                
        except Exception as e:
            logger.error(f"Error executing node {node_name}: {e}")
            return NodeResult(
                node_name=node_name,
                status="error",
                output_files=[],
                error_message=str(e)
            )
    
    def _get_node_specific_message(self, node_name: str) -> str:
        """Get node-specific message for display."""
        messages = {
            "node1": NODE1_START_MESSAGE,
            "node2": NODE2_START_MESSAGE,
            "node3": NODE3_START_MESSAGE,
            "node4": NODE4_START_MESSAGE,
            "node5": NODE5_START_MESSAGE
        }
        return messages.get(node_name, "")
    
    async def _complete_workflow_execution(self) -> None:
        """Complete the workflow execution and transition to continue prompt."""
        try:
            # Generate workflow completion message
            executed_nodes = list(self.state_manager.state.node_results.keys())
            total_files = len(self.output_files)
            
            # Create workflow summary
            if self.state_manager.state.start_time:
                workflow_summary = generate_workflow_summary(
                    self.state_manager.state.workflow_config,
                    self.state_manager.state.node_results,
                    self.state_manager.state.start_time,
                    datetime.now()
                )
            else:
                workflow_summary = "Workflow completed successfully."
            
            completion_message = WORKFLOW_COMPLETE_MESSAGE.format(
                executed_nodes=", ".join(executed_nodes),
                total_files=total_files,
                output_files_list=format_output_files_list(self.output_files, self.state_manager.state.node_results),
                workflow_summary=workflow_summary
            )
            
            print(f"\n{completion_message}")
            
            # Transition to continue prompt
            self.state_manager.transition(HLAFineMappingState.CONTINUE_PROMPT)
            
            print(f"\n{CONTINUE_PROMPT_MESSAGE}")
            
        except Exception as e:
            logger.error(f"Error completing workflow execution: {e}")
            print(f"\n❌ Error completing workflow: {e}")
    
    def _generate_completion_message(self) -> str:
        """Generate final completion message."""
        try:
            total_workflows = len(self.state_manager.state.node_results)
            total_files = len(self.output_files)
            
            if self.state_manager.state.start_time:
                duration = datetime.now() - self.state_manager.state.start_time
                session_duration = str(duration).split('.')[0]  # Remove microseconds
            else:
                session_duration = "Unknown"
            
            if self.state_manager.state.is_standalone:
                completion_context = "Thank you for using the HLA Fine Mapping Agent!"
            else:
                completion_context = f"Returning to {self.state_manager.state.requester_agent}."
            
            return AGENT_FINISHED_MESSAGE.format(
                total_workflows=total_workflows,
                total_files=total_files,
                session_duration=session_duration,
                completion_context=completion_context
            )
            
        except Exception as e:
            logger.error(f"Error generating completion message: {e}")
            return "HLA Fine Mapping Agent completed with errors."
    
    def _generate_session_result(self) -> Dict[str, Any]:
        """Generate final session result."""
        try:
            return {
                "status": "completed" if self.state_manager.is_session_complete() else "incomplete",
                "session_id": self.state_manager.state.session_id,
                "requester_agent": self.state_manager.state.requester_agent,
                "task_id": self.state_manager.state.task_id,
                "is_standalone": self.state_manager.state.is_standalone,
                "workflow_status": self.state_manager.get_workflow_status(),
                "output_files": self.output_files,
                "node_results": {name: result.__dict__ for name, result in self.state_manager.state.node_results.items()},
                "conversation_count": len(self.state_manager.state.conversation_history),
                "has_error": self.state_manager.state.has_error,
                "error_message": self.state_manager.state.error_message
            }
        except Exception as e:
            logger.error(f"Error generating session result: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information for supervisor integration."""
        return self.state_manager.get_session_info()
    
    async def cleanup(self) -> None:
        """Clean up resources."""
        try:
            # Clean up any resources if needed
            logger.info("HLA Fine Mapping Agent cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


# Convenience function for creating the agent
def create_hla_fine_mapping_agent(supervisor_handoff_callback: Optional[Callable] = None) -> HLAFineMappingAgent:
    """
    Create a HLA fine mapping agent instance.
    
    Args:
        supervisor_handoff_callback: Callback for supervisor handoff
        
    Returns:
        HLAFineMappingAgent instance
    """
    return HLAFineMappingAgent(supervisor_handoff_callback=supervisor_handoff_callback)