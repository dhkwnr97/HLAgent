"""
Workflow management for HLA Imputation Agent.

This module defines the specific workflows for different HLA imputation tools
and manages the execution flow from tool selection to output generation.
"""

import asyncio
from typing import List, Optional, Callable
from .agent_types import (
    HLAImputationState, HLAImputationTool, HLAToolInfo, 
    ResponseType, AgentResponse
)
from .states import StateManager
from .tools import HLAToolScanner, HLAWorkchainManager, HLAToolSelector
from .prompts import HLA_IMPUTATION_PROMPTS
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class HLAImputationWorkflow:
    """
    Main workflow manager for HLA imputation processes.
    
    This class orchestrates the complete workflow from tool scanning
    through execution and output generation.
    """
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.state_manager = StateManager()
        self.tool_scanner = HLAToolScanner()
        self.workchain_manager = HLAWorkchainManager(supervisor_handoff_callback)
        
    async def execute_idle_workflow(self) -> AgentResponse:
        """
        Execute the IDLE state workflow - scan tools and show options.
        
        Returns:
            AgentResponse with tool selection options
        """
        try:
            logger.info("Starting IDLE workflow - scanning available tools")
            self.state_manager.transition(HLAImputationState.TOOL_SELECTION)
            
            # Scan available tools
            available_tools = self.tool_scanner.scan_available_tools()
            
            if not available_tools:
                return AgentResponse(
                    response_type=ResponseType.ERROR,
                    message="❌ No supported HLA imputation tools found.",
                    requires_input=False,
                    session_complete=True
                )
            
            # Build tool display message
            message = self._build_tool_selection_message(available_tools)
            
            return AgentResponse(
                response_type=ResponseType.REQUEST_INPUT,
                message=message,
                requires_input=True,
                data={"available_tools": [tool.name for tool in available_tools]}
            )
            
        except Exception as e:
            logger.error(f"Error in IDLE workflow: {e}")
            self.state_manager.set_error(str(e))
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=f"❌ Error scanning tools: {e}",
                requires_input=False,
                session_complete=True
            )
    
    def _build_tool_selection_message(self, available_tools: List[HLAToolInfo]) -> str:
        """Build the tool selection message with available options."""
        message_parts = [
            HLA_IMPUTATION_PROMPTS["welcome_message"],
            HLA_IMPUTATION_PROMPTS["tool_scanning"],
            HLA_IMPUTATION_PROMPTS["available_tools_header"]
        ]
        
        # Add each tool with formatted information
        for i, tool in enumerate(available_tools, 1):
            advantages_str = " • ".join(tool.advantages)
            tool_info = HLA_IMPUTATION_PROMPTS["tool_info_template"].format(
                number=i,
                display_name=tool.display_name,
                name=tool.name,
                description=tool.description,
                input_description=tool.input_description,
                advantages=advantages_str,
                status="Supported" if tool.is_supported else "Not Supported"
            )
            message_parts.append(tool_info)
        
        message_parts.append(HLA_IMPUTATION_PROMPTS["tool_selection_prompt"])
        
        return "\n".join(message_parts)
    
    async def handle_tool_selection(self, user_input: str) -> AgentResponse:
        """
        Handle user tool selection input.
        
        Args:
            user_input: User's tool selection
            
        Returns:
            AgentResponse with next workflow step
        """
        try:
            available_tools = self.tool_scanner.scan_available_tools()
            selected_tool = HLAToolSelector.parse_user_selection(user_input, available_tools)
            
            if not selected_tool:
                return AgentResponse(
                    response_type=ResponseType.REQUEST_INPUT,
                    message=HLA_IMPUTATION_PROMPTS["invalid_tool_selection"].format(
                        selection=user_input
                    ),
                    requires_input=True
                )
            
            if not HLAToolSelector.validate_tool_selection(selected_tool):
                return AgentResponse(
                    response_type=ResponseType.REQUEST_INPUT,
                    message=HLA_IMPUTATION_PROMPTS["tool_not_supported"].format(
                        tool=selected_tool.name
                    ),
                    requires_input=True
                )
            
            # Store selected tool
            tool_enum = HLAImputationTool(selected_tool.name)
            self.state_manager.set_selected_tool(tool_enum, selected_tool)
            self.state_manager.transition(HLAImputationState.INPUT_VALIDATION)
            
            # Show tool-specific input requirements
            return await self._show_input_requirements(selected_tool)
            
        except Exception as e:
            logger.error(f"Error handling tool selection: {e}")
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=f"❌ Error processing selection: {e}",
                requires_input=False,
                session_complete=True
            )
    
    async def _show_input_requirements(self, tool_info: HLAToolInfo) -> AgentResponse:
        """Show input requirements for the selected tool."""
        self.state_manager.transition(HLAImputationState.READY_CHECK)
        
        # Get tool-specific input requirements message
        if tool_info.name == "cookhla":
            requirements_msg = HLA_IMPUTATION_PROMPTS["cookhla_input_requirements"]
        elif tool_info.name == "hlahd":
            requirements_msg = HLA_IMPUTATION_PROMPTS["hlahd_input_requirements"]
        elif tool_info.name == "optitype":
            requirements_msg = HLA_IMPUTATION_PROMPTS["optitype_input_requirements"]
        else:
            requirements_msg = f"Input requirements for {tool_info.display_name}:\n{tool_info.input_description}"
        
        # Combine selection confirmation with requirements
        message = HLA_IMPUTATION_PROMPTS["tool_selected"].format(
            display_name=tool_info.display_name,
            description=tool_info.description
        ) + "\n\n" + requirements_msg + "\n\n" + HLA_IMPUTATION_PROMPTS["ready_options"]
        
        return AgentResponse(
            response_type=ResponseType.REQUEST_INPUT,
            message=message,
            requires_input=True
        )
    
    async def handle_ready_response(self, user_input: str) -> AgentResponse:
        """
        Handle user's ready/not ready/other types response.
        
        Args:
            user_input: User's response
            
        Returns:
            AgentResponse with next workflow step
        """
        try:
            user_input = user_input.lower().strip()
            
            if user_input == "ready":
                return await self._proceed_with_execution()
            
            elif user_input == "not ready":
                self.state_manager.transition(HLAImputationState.CANCELLED)
                return AgentResponse(
                    response_type=ResponseType.INFO,
                    message=HLA_IMPUTATION_PROMPTS["not_ready_message"],
                    requires_input=False,
                    session_complete=True
                )
            
            elif user_input == "other types":
                return await self._handle_file_conversion()
            
            else:
                return AgentResponse(
                    response_type=ResponseType.REQUEST_INPUT,
                    message=HLA_IMPUTATION_PROMPTS["invalid_ready_response"],
                    requires_input=True
                )
                
        except Exception as e:
            logger.error(f"Error handling ready response: {e}")
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=f"❌ Error processing response: {e}",
                requires_input=False,
                session_complete=True
            )
    
    async def _handle_file_conversion(self) -> AgentResponse:
        """Handle file conversion workflow."""
        try:
            self.state_manager.transition(HLAImputationState.FILE_CONVERSION)
            
            if self.supervisor_handoff_callback:
                logger.info("Handing off to file converter via supervisor")
                
                # Handoff to file converter
                await self.supervisor_handoff_callback(
                    agent_name="fileconverter",
                    task_description="Convert genotype data for HLA imputation",
                    context="User has different format files that need conversion"
                )
                
                # After file conversion, return to ready check
                return await self._show_input_requirements(
                    self.state_manager.get_selected_tool_info()
                )
            
            else:
                return AgentResponse(
                    response_type=ResponseType.ERROR,
                    message="❌ File conversion required but no supervisor available.",
                    requires_input=False,
                    session_complete=True
                )
                
        except Exception as e:
            logger.error(f"Error handling file conversion: {e}")
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=f"❌ File conversion failed: {e}",
                requires_input=False,
                session_complete=True
            )
    
    async def _proceed_with_execution(self) -> AgentResponse:
        """Proceed with workchain execution."""
        try:
            tool_info = self.state_manager.get_selected_tool_info()
            
            self.state_manager.transition(HLAImputationState.PARAMETER_HANDOFF)
            
            # Show parameter modification message
            param_msg = HLA_IMPUTATION_PROMPTS["parameter_modification"]
            print(param_msg)
            
            # Execute workchain
            self.state_manager.transition(HLAImputationState.EXECUTION)
            execution_msg = HLA_IMPUTATION_PROMPTS["execution_started"].format(
                tool_name=tool_info.display_name
            )
            print(execution_msg)
            
            # Execute the workchain
            output_files = await self.workchain_manager.execute_tool_workchain(tool_info)
            
            # Store output files
            self.state_manager.clear_output_files()
            for file_path in output_files:
                self.state_manager.add_output_file(file_path)
            
            self.state_manager.transition(HLAImputationState.COMPLETED)
            
            # Generate completion message
            if output_files:
                files_list = "\n".join([
                    HLA_IMPUTATION_PROMPTS["file_list_template"].format(filename=file)
                    for file in output_files
                ])
                
                completion_msg = HLA_IMPUTATION_PROMPTS["execution_complete"] + "\n" + files_list
                completion_msg += "\n\n" + HLA_IMPUTATION_PROMPTS["completion_summary"].format(
                    tool_name=tool_info.display_name,
                    file_count=len(output_files)
                )
            else:
                completion_msg = HLA_IMPUTATION_PROMPTS["no_output_files"]
            
            return AgentResponse(
                response_type=ResponseType.COMPLETION,
                message=completion_msg,
                requires_input=False,
                session_complete=True,
                data={"output_files": output_files}
            )
            
        except Exception as e:
            logger.error(f"Error in execution workflow: {e}")
            self.state_manager.set_error(str(e))
            return AgentResponse(
                response_type=ResponseType.ERROR,
                message=HLA_IMPUTATION_PROMPTS["error_message"].format(error=str(e)),
                requires_input=False,
                session_complete=True
            )
    
    def get_current_state(self) -> HLAImputationState:
        """Get current workflow state."""
        return self.state_manager.get_current_state().current_state
    
    def get_output_files(self) -> List[str]:
        """Get list of generated output files."""
        return self.state_manager.get_output_files()
    
    def is_session_complete(self) -> bool:
        """Check if workflow session is complete."""
        return self.state_manager.is_session_complete()
    
    def get_state_info(self) -> dict:
        """Get detailed state information."""
        return self.state_manager.get_state_info()