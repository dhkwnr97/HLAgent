"""
File Converter Agent.

A professional file converter agent using langgraph.prebuilt create_react_agent.
Supports genotype file conversion and HLA imputation tool output conversion.
"""

import os
import asyncio
from typing import Dict, Any, List, Optional, Callable

from langgraph.prebuilt import create_react_agent

from src.core.llm_config import get_llm
from .agent_types import ConverterState, ConversionMode
from .states import StateManager
from .tools import FileConverterTools
from .prompts import FILECONVERTER_PROMPTS
from .workflows import GenotypeWorkflow, ImputationWorkflow
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


class FileConverterAgent:
    """
    Professional File Converter Agent using LangGraph create_react_agent.
    
    Features:
    - Modular genotype file conversion workflows
    - HLA imputation tool output conversion workflows
    - LangGraph reactive agent architecture
    - Clean separation of concerns
    """
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        """Initialize the file converter agent."""
        self.llm = get_llm()
        self.state_manager = StateManager()
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.tools = FileConverterTools(supervisor_handoff_callback=supervisor_handoff_callback)
        self.output_files = []
        
        # Initialize modular workflows with react_agent
        self.genotype_workflow = GenotypeWorkflow(self.tools, self)
        self.imputation_workflow = ImputationWorkflow(self.tools)
        
        # Create reactive agent with tools for LLM-powered analysis
        self.system_prompt = FILECONVERTER_PROMPTS["system_prompt"]
        self.react_agent = self._create_react_agent()
    
    def _create_react_agent(self):
        """Create LangGraph reactive agent with conversion tools."""
        from .langchain_tools import get_all_conversion_tools
        tools = get_all_conversion_tools(self.tools)
        
        return create_react_agent(
            model=self.llm,
            tools=tools,
            prompt=self.system_prompt
        )
    
    def _initialize_session(self, requester_agent: str = "", task_id: str = ""):
        """Initialize session and clear output files."""
        logger.info("Initializing file converter session")
        
        self.state_manager.initialize_session(requester_agent, task_id)
        self.output_files = []
        self.state_manager.transition(ConverterState.IDLE)
    
    async def _show_welcome_and_get_mode(self) -> Optional[ConversionMode]:
        """Show welcome message and get conversion mode from user."""
        print(FILECONVERTER_PROMPTS["welcome_message"])
        print(FILECONVERTER_PROMPTS["mode_selection"])
        
        while True:
            user_input = await self._get_user_input()
            
            if "genotype converting" in user_input.lower():
                return ConversionMode.GENOTYPE
            elif "imputation converting" in user_input.lower():
                return ConversionMode.IMPUTATION
            elif user_input.lower() == "done!":
                return None
            else:
                print(FILECONVERTER_PROMPTS["invalid_input"].format(user_input=user_input))
    
    async def _get_user_input(self, prompt: str = "To File Converter Agent: ") -> str:
        """Get user input (async wrapper for input())."""
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: input(prompt).strip()
        )
    
    async def _run_conversion_workflow(self, mode: ConversionMode) -> List[str]:
        """Run the appropriate conversion workflow based on mode."""
        self.state_manager.transition(ConverterState.PROCESSING)
        
        try:
            if mode == ConversionMode.GENOTYPE:
                output_files = await self.genotype_workflow.execute()
            elif mode == ConversionMode.IMPUTATION:
                output_files = await self.imputation_workflow.execute()
            else:
                return []
            
            # Store output files
            self.output_files.extend(output_files)
            for file_path in output_files:
                self.state_manager.get_current_state().add_output_file(file_path)
            
            return output_files
            
        except Exception as e:
            logger.error(f"Conversion workflow failed: {e}")
            print(f"❌ Conversion failed: {e}")
            return []
    
    def _show_completion_message(self, output_files: List[str]):
        """Show completion message with output files."""
        if output_files:
            files_display = self.tools.format_output_files(output_files)
            completion_msg = FILECONVERTER_PROMPTS["conversion_complete"].format(
                output_files=files_display
            )
            print(completion_msg)
        else:
            print(FILECONVERTER_PROMPTS["workflow_error"].format(
                error_message="No output files were generated"
            ))
    
    async def _ask_continue(self) -> bool:
        """Ask user if they want to continue or finish."""
        continue_input = await self._get_user_input()
        return continue_input.lower() != "done!"
    
    async def run(self, requester_agent: str = "", task_id: str = "") -> List[str]:
        """
        Run the main file converter workflow.
        
        Clean, simplified workflow following exact my_request_6.md requirements:
        1. Initialize output files list
        2. Show welcome message with available services
        3. Get mode selection (genotype/imputation/done)
        4. Execute appropriate workflow
        5. Show results and ask for continuation
        
        Args:
            requester_agent: Name of requesting agent (empty for standalone)
            task_id: Task identifier
            
        Returns:
            List of output file paths
        """
        try:
            # Step 1: Initialize session and clear output files (myoutputfile list)
            self._initialize_session(requester_agent, task_id)
            
            # Main workflow loop
            while True:
                # Step 2: Show welcome and get mode selection
                mode = await self._show_welcome_and_get_mode()
                
                if mode is None:
                    # User entered "Done!" - exit workflow
                    self.state_manager.transition(ConverterState.COMPLETED)
                    print(FILECONVERTER_PROMPTS["goodbye_message"])
                    break
                
                # Step 3: Execute conversion workflow based on mode
                output_files = await self._run_conversion_workflow(mode)
                
                # Step 4: Show completion message with output files
                self._show_completion_message(output_files)
                
                # Step 5: Ask for continuation
                if not await self._ask_continue():
                    self.state_manager.transition(ConverterState.COMPLETED)
                    print(FILECONVERTER_PROMPTS["goodbye_message"])
                    break
            
            return self.output_files
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            print(f"❌ Error: {e}")
            return []
    
    async def chat_loop(self, requester_agent: str = "", task_id: str = "") -> List[str]:
        """
        Main entry point for both standalone and supervised operation.
        
        Args:
            requester_agent: Name of requesting agent
            task_id: Task identifier
            
        Returns:
            List of output file paths
        """
        print("\n=== Professional File Converter Agent ===")
        
        try:
            output_files = await self.run(requester_agent, task_id)
            
            if output_files:
                print(f"\n✅ Conversion completed successfully!")
                print(f"Generated {len(output_files)} output files.")
            else:
                print("\n❌ Conversion was cancelled or failed.")
            
            return output_files
            
        except KeyboardInterrupt:
            print("\n\n🛑 Operation cancelled by user.")
            return []
        except Exception as e:
            logger.error(f"Chat loop error: {e}")
            print(f"\n❌ Error: {e}")
            return []
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get current agent state information."""
        return self.state_manager.get_state_info()


# Convenience function for creating the agent
def create_file_converter_agent(supervisor_handoff_callback: Optional[Callable] = None) -> FileConverterAgent:
    """
    Create a file converter agent instance.
    
    Args:
        supervisor_handoff_callback: Callback for supervisor handoff
        
    Returns:
        FileConverterAgent instance
    """
    return FileConverterAgent(supervisor_handoff_callback=supervisor_handoff_callback)