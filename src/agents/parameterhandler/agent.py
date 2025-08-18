"""
Parameter Handler Agent.

A professional YAML parameter file modification agent for bioinformatics workflows.
Supports both standalone operation and integration with supervisor agent workflows.
"""

import os
import json
import asyncio
from typing import Dict, Any, List, Optional, AsyncGenerator
from src.core.llm_config import get_llm

from .agent_types import AgentState, AgentResponse, ResponseType, YamlModificationRequest
from .states import StateManager, SessionState
from .tools import (
    copy_yaml_file, read_yaml_with_line_numbers, modify_yaml_line,
    parse_edit_request, validate_yaml_syntax, get_working_yaml_path, read_yaml_content
)
from .prompts import (
    WELCOME_MESSAGE, YAML_DISPLAY_HEADER, MODIFICATION_SUCCESS, MODIFICATION_ERROR,
    CONFIRMATION_MESSAGE, TASK_COMPLETION, HELP_MESSAGE, ERROR_MESSAGES,
    SEPARATOR_LINE, YAML_SEPARATOR, AGENT_PROMPTS
)


class ParameterHandlerAgent:
    """
    Parameter Handler Agent for YAML file modifications.
    
    Features:
    - Interactive YAML parameter modification
    - Professional bioinformatics tool parameter handling
    - Standalone and supervisor-integrated operation
    - Comprehensive error handling and validation
    """
    
    def __init__(self):
        self.llm = get_llm()
        self.state_manager = StateManager()
        
    async def start_session(self, yaml_path: str, requester: str = "", task_id: str = "") -> AgentResponse:
        """
        Start a new YAML modification session.
        
        Args:
            yaml_path: Path to the original YAML file (_orig.yaml)
            requester: Name of the requesting agent (empty for standalone)
            task_id: Unique task identifier
            
        Returns:
            AgentResponse with session initialization result
        """
        try:
            # Initialize session
            response = self.state_manager.initialize_session(yaml_path, requester, task_id)
            if response.response_type == ResponseType.ERROR:
                return response
                
            # Copy the original file to working file
            copy_result = copy_yaml_file.invoke({"original_path": yaml_path})
            if "Error" in copy_result:
                return AgentResponse(
                    response_type=ResponseType.ERROR,
                    message=copy_result,
                    requires_input=False
                )
            
            # Set working file path
            working_path = get_working_yaml_path(yaml_path)
            self.state_manager.state.working_yaml_path = working_path
            
            # Read the file content
            self.state_manager.state.yaml_content = read_yaml_content(working_path)
            
            # Transition to show content state
            self.state_manager.transition(AgentState.SHOW_CONTENT)
            
            # Display the file content
            content_display = read_yaml_with_line_numbers.invoke({"yaml_path": yaml_path})
            
            if self.state_manager.state.is_standalone:
                welcome_msg = WELCOME_MESSAGE
            else:
                welcome_msg = f"🔧 Parameter editing requested by: {requester}"
            
            full_message = f"{welcome_msg}\n\n" + YAML_DISPLAY_HEADER.format(
                separator=YAML_SEPARATOR,
                content=content_display
            )
            
            # Transition to interactive editing
            self.state_manager.transition(AgentState.INTERACTIVE_EDIT)
            
            return AgentResponse(
                response_type=ResponseType.REQUEST_INPUT,
                message=full_message + "\nWhat would you like to change? (or type 'help' for examples)",
                requires_input=True,
                data={"file_path": working_path, "line_count": len(self.state_manager.state.yaml_content)}
            )
            
        except Exception as e:
            self.state_manager.state.set_error(str(e))
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=ERROR_MESSAGES["general_error"].format(error=str(e)),
                requires_input=False
            )
    
    async def process_user_input(self, user_input: str) -> AgentResponse:
        """
        Process user input during interactive editing session.
        
        Args:
            user_input: User's input command
            
        Returns:
            AgentResponse with processing result
        """
        try:
            user_input = user_input.strip()
            
            if not user_input:
                return AgentResponse(
                    response_type=ResponseType.REQUEST_INPUT,
                    message="Please enter a command. Type 'help' for examples.",
                    requires_input=True
                )
            
            # Handle completion request
            if user_input.lower() == "done!":
                return await self._handle_completion_request()
            
            # Handle confirmation responses
            if self.state_manager.state.awaiting_confirmation:
                return await self._handle_confirmation(user_input)
            
            # Handle help request
            if user_input.lower() in ["help", "?", "commands"]:
                return AgentResponse(
                    response_type=ResponseType.INFO,
                    message=HELP_MESSAGE + "\nWhat would you like to change?",
                    requires_input=True
                )
            
            # Handle file display request
            if user_input.lower() in ["show file", "show content", "display", "view"]:
                return await self._show_current_content()
            
            # Handle modification request
            return await self._handle_modification_request(user_input)
            
        except Exception as e:
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=ERROR_MESSAGES["general_error"].format(error=str(e)),
                requires_input=True
            )
    
    async def _handle_modification_request(self, user_input: str) -> AgentResponse:
        """Handle YAML modification requests using LLM parsing."""
        try:
            # Use LLM to parse the modification request
            parsing_prompt = AGENT_PROMPTS["parse_modification_request"].format(user_input=user_input)
            
            # Get LLM response
            llm_response = await self.llm.ainvoke(parsing_prompt)
            edits_json = llm_response.content.strip()
            
            # Clean up the response (remove any markdown formatting)
            if edits_json.startswith('```json'):
                edits_json = edits_json[7:]
            if edits_json.endswith('```'):
                edits_json = edits_json[:-3]
            edits_json = edits_json.strip()
            
            try:
                edits = json.loads(edits_json)
            except json.JSONDecodeError:
                # Fallback to original parsing if LLM fails
                edits_json = parse_edit_request.invoke({"user_input": user_input})
                edits = json.loads(edits_json)
            
            if not edits:
                return AgentResponse(
                    response_type=ResponseType.REQUEST_INPUT,
                    message=ERROR_MESSAGES["parse_error"] + "\nWhat would you like to change?",
                    requires_input=True
                )
            
            # Remove duplicate edits (same line number)
            unique_edits = {}
            for edit in edits:
                line_number = edit["line_number"]
                # Keep the last edit for each line number
                unique_edits[line_number] = edit
            
            # Apply each unique edit
            results = []
            for line_number, edit in unique_edits.items():
                new_value = str(edit["new_value"])  # Ensure it's always a string
                
                # Validate line number
                if line_number < 1 or line_number > len(self.state_manager.state.yaml_content):
                    results.append(f"❌ Line {line_number} is out of range")
                    continue
                
                # Get original line for display
                original_line = self.state_manager.state.yaml_content[line_number - 1].strip()
                
                # Apply modification
                result = modify_yaml_line.invoke({
                    "yaml_path": self.state_manager.state.working_yaml_path,
                    "line_number": line_number,
                    "new_value": new_value
                })
                
                if "Successfully" in result:
                    results.append(MODIFICATION_SUCCESS.format(
                        line_number=line_number,
                        old_value=original_line,
                        new_value=new_value
                    ))
                    # Update cached content after each modification
                    self.state_manager.state.yaml_content = read_yaml_content(
                        self.state_manager.state.working_yaml_path
                    )
                else:
                    results.append(MODIFICATION_ERROR.format(
                        line_number=line_number,
                        error=result
                    ))
            
            response_message = "\n\n".join(results)
            
            # Validate YAML syntax
            validation = validate_yaml_syntax.invoke({"yaml_path": self.state_manager.state.working_yaml_path})
            if "error" in validation.lower():
                response_message += f"\n\n⚠️  Warning: {validation}"
            
            return AgentResponse(
                response_type=ResponseType.REQUEST_INPUT,
                message=response_message,
                requires_input=True
            )
            
        except Exception as e:
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=ERROR_MESSAGES["general_error"].format(error=str(e)),
                requires_input=True
            )
    
    async def _handle_completion_request(self) -> AgentResponse:
        """Handle completion request ("Done!")."""
        try:
            # Show final content and ask for confirmation
            content_display = read_yaml_with_line_numbers.invoke({
                "yaml_path": self.state_manager.state.working_yaml_path
            })
            
            confirmation_msg = CONFIRMATION_MESSAGE.format(
                separator=YAML_SEPARATOR,
                content=content_display
            )
            
            self.state_manager.state.awaiting_confirmation = True
            self.state_manager.transition(AgentState.CONFIRMATION)
            
            return AgentResponse(
                response_type=ResponseType.CONFIRMATION,
                message=confirmation_msg,
                requires_input=True
            )
            
        except Exception as e:
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=ERROR_MESSAGES["general_error"].format(error=str(e)),
                requires_input=True
            )
    
    async def _handle_confirmation(self, user_input: str) -> AgentResponse:
        """Handle user confirmation (Yes/No)."""
        user_input = user_input.lower().strip()
        
        if user_input in ["yes", "y", "confirm", "ok"]:
            # Complete the task
            self.state_manager.state.task_complete = True
            self.state_manager.state.awaiting_confirmation = False
            self.state_manager.transition(AgentState.COMPLETED)
            
            return AgentResponse(
                response_type=ResponseType.COMPLETION,
                message=TASK_COMPLETION,
                requires_input=False,
                session_complete=True,
                data={
                    "working_file": self.state_manager.state.working_yaml_path,
                    "requester": self.state_manager.state.requester_agent,
                    "task_id": self.state_manager.state.task_id
                }
            )
        
        elif user_input in ["no", "n", "cancel", "continue"]:
            # Return to editing
            self.state_manager.state.awaiting_confirmation = False
            self.state_manager.transition(AgentState.INTERACTIVE_EDIT)
            
            return AgentResponse(
                response_type=ResponseType.REQUEST_INPUT,
                message="Continuing with modifications. What else would you like to change?",
                requires_input=True
            )
        
        else:
            return AgentResponse(
                response_type=ResponseType.CONFIRMATION,
                message="Please respond with 'Yes' to confirm or 'No' to continue editing:",
                requires_input=True
            )
    
    async def _show_current_content(self) -> AgentResponse:
        """Show current file content."""
        try:
            content_display = read_yaml_with_line_numbers.invoke({
                "yaml_path": self.state_manager.state.working_yaml_path
            })
            
            message = YAML_DISPLAY_HEADER.format(
                separator=YAML_SEPARATOR,
                content=content_display
            ) + "\nWhat would you like to change?"
            
            return AgentResponse(
                response_type=ResponseType.REQUEST_INPUT,
                message=message,
                requires_input=True
            )
            
        except Exception as e:
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=ERROR_MESSAGES["general_error"].format(error=str(e)),
                requires_input=True
            )
    
    async def chat_loop(self, yaml_path: str, requester: str = "", task_id: str = "") -> Dict[str, Any]:
        """
        Main interactive chat loop for standalone operation.
        
        Args:
            yaml_path: Path to the YAML file to modify
            requester: Name of the requesting agent (empty for standalone)
            task_id: Unique task identifier
            
        Returns:
            Final session result
        """
        try:
            # Start the session
            response = await self.start_session(yaml_path, requester, task_id)
            print(response.message)
            
            if response.response_type == ResponseType.ERROR:
                return {"status": "error", "message": response.message}
            
            # Main interaction loop
            while not self.state_manager.is_session_complete():
                try:
                    user_input = input("\nTo Parameter Handler Agent: ").strip()
                    
                    if user_input.lower() in ["exit", "quit", "abort"]:
                        print("Session aborted.")
                        return {"status": "aborted", "message": "Session aborted by user"}
                    
                    response = await self.process_user_input(user_input)
                    print(f"\n{response.message}")
                    
                    if response.session_complete:
                        break
                        
                except KeyboardInterrupt:
                    print("\n\nSession interrupted.")
                    return {"status": "interrupted", "message": "Session interrupted by user"}
            
            # Return final result
            state = self.state_manager.get_current_state()
            return {
                "status": "completed" if state.task_complete else "incomplete",
                "working_file": state.working_yaml_path,
                "original_file": state.original_yaml_path,
                "requester": state.requester_agent,
                "task_id": state.task_id
            }
            
        except Exception as e:
            error_msg = f"Error in chat loop: {str(e)}"
            print(f"\n❌ {error_msg}")
            return {"status": "error", "message": error_msg}
    
    # Methods for supervisor integration
    async def handle_supervisor_request(self, request: YamlModificationRequest) -> Dict[str, Any]:
        """
        Handle a modification request from the supervisor agent.
        
        Args:
            request: YamlModificationRequest object
            
        Returns:
            Dict with session result
        """
        return await self.chat_loop(
            request.original_yaml_path,
            request.requester_agent,
            request.task_id
        )
    
    def get_session_info(self) -> Dict[str, Any]:
        """Get current session information."""
        state = self.state_manager.get_current_state()
        return {
            "current_state": state.current_state.value,
            "is_active": not self.state_manager.is_session_complete(),
            "file_info": state.get_file_info(),
            "requester": state.requester_agent,
            "task_id": state.task_id,
            "is_standalone": state.is_standalone
        }