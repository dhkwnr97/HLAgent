"""
Genotype Phasing Agent.

A professional genotype phasing agent using BEAGLE tool with StateGraph workflow.
Supports VCF, PLINK, and BEAGLE input formats.
"""

import os
from dotenv import load_dotenv

import asyncio
from typing import Dict, Any, List, Optional, Callable

from src.core.llm_config import get_llm
from .agent_types import (
    PhasingState, PhasingResponse, ResponseType, InputFormat,
    PhasingWorkflowState, InputValidationResult
)
from .states import PhasingStateManager
from .tools import PhasingTools
from .prompts import PHASING_PROMPTS
from src.core.workchain import create_workchain
from src.utils.logger import setup_logger


logger = setup_logger(__name__)


load_dotenv()


class GenotypePhasingAgent:
    """
    Interactive Genotype Phasing Agent.
    
    This agent handles genotype phasing using BEAGLE tool with support for:
    - VCF, PLINK, and BEAGLE input formats
    - Interactive user input for workflow control
    - Parameter modification via workchain
    - Output file tracking and return
    - Both standalone and supervisor-integrated operation
    """
    
    def __init__(self, supervisor_handoff_callback: Optional[Callable] = None):
        self.llm = get_llm()
        self.state_manager = PhasingStateManager()
        self._supervisor_handoff_callback = supervisor_handoff_callback
        self.workchain = create_workchain(
            supervisor_handoff_callback=supervisor_handoff_callback
        )
        self.output_files = []
    
    @property
    def supervisor_handoff_callback(self) -> Optional[Callable]:
        """Get supervisor handoff callback."""
        return self._supervisor_handoff_callback
    
    @supervisor_handoff_callback.setter
    def supervisor_handoff_callback(self, callback: Optional[Callable]):
        """Set supervisor handoff callback and update workchain."""
        self._supervisor_handoff_callback = callback
        # Update workchain callback when supervisor callback is set
        if self.workchain:
            self.workchain.supervisor_handoff_callback = callback
    
    def _initialize_session(self, requester_agent: str = "", task_id: str = ""):
        """Initialize session and clear output files."""
        logger.info("Initializing genotype phasing session")
        
        # Initialize session
        self.state_manager.initialize_session(requester_agent, task_id)
        self.state_manager.clear_output_files()
        self.output_files = []
        self.state_manager.transition(PhasingState.IDLE)
    
    async def _show_welcome_and_format_info(self):
        """Show welcome message and input format information."""
        logger.info("Showing welcome and format information")
        
        self.state_manager.transition(PhasingState.CHECKING_INPUT)
        
        welcome_msg = PHASING_PROMPTS["welcome_message"]
        format_info = PHASING_PROMPTS["input_format_info"]
        ready_prompt = PHASING_PROMPTS["ready_prompt"]
        
        full_message = f"{welcome_msg}\n\n{format_info}\n\n{ready_prompt}"
        print(full_message)
        
        return full_message
    
    async def _get_user_input(self) -> str:
        """Get user input (async wrapper for input())."""
        return await asyncio.get_event_loop().run_in_executor(
            None, lambda: input("To Genotype Phasing Agent: ").strip()
        )
    
    async def _handle_user_input(self, user_input: str) -> str:
        """
        Handle user input during workflow.
        
        Args:
            user_input: User's input
            
        Returns:
            Action to take ("ready", "not_ready", "other_types", "invalid")
        """
        user_input = user_input.lower().strip()
        
        if user_input == "ready":
            return "ready"
        elif user_input == "not ready":
            return "not_ready"
        elif user_input == "other types":
            return "other_types"
        else:
            print(PHASING_PROMPTS["invalid_input"].format(user_input=user_input))
            return "invalid"
    
    async def _handle_file_conversion(self) -> bool:
        """Handle file conversion handoff."""
        logger.info("Handling file conversion")
        
        try:
            if self.supervisor_handoff_callback:
                print(PHASING_PROMPTS["file_conversion_needed"])
                
                # Handoff to file converter
                await self.supervisor_handoff_callback(
                    agent_name="fileconverter",
                    task_description="Convert genotype data to PLINK format (.bed, .bim, .fam)",
                    context="User needs file conversion for genotype phasing"
                )
                
                return True
            else:
                print("File conversion required but no supervisor available")
                return False
        except Exception as e:
            logger.error(f"File conversion handoff failed: {e}")
            print(f"File conversion handoff failed: {e}")
            return False
    
    async def _execute_workchain(self) -> List[str]:
        """Execute workchain for parameter handling and phasing."""
        logger.info("Executing workchain for parameter modification and phasing")
        
        try:
            self.state_manager.transition(PhasingState.PARAMETER_HANDOFF)
            print(PHASING_PROMPTS["parameter_modification"])
            
            # Execute workchain for parameter handling
            output_files = await self.workchain.execute_workchain(
                yaml_path=os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/HATK/Runners/phasing_run_config_orig.yaml"),
                python_script_path=os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/HATK/Runners/run_phasing.py"),
                output_file_extensions=[".bgl.phased", ".aa", ".markers"],
                output_file_prefixes=[]
            )
            
            # Store output files
            self.output_files = output_files
            for file_path in output_files:
                self.state_manager.add_output_file(file_path)
            
            return output_files
            
        except Exception as e:
            logger.error(f"Workchain execution failed: {e}")
            self.state_manager.set_error(str(e))
            print(f"Workchain execution failed: {e}")
            return []
    
    def _display_completion_message(self, output_files: List[str]):
        """Display completion message with output files."""
        logger.info("Displaying completion message")
        
        self.state_manager.transition(PhasingState.COMPLETED)
        
        if output_files:
            # Format output files for display
            files_display = "\n".join([f"• {file}" for file in output_files])
            message = PHASING_PROMPTS["phasing_complete"] + "\n" + files_display
            print(f"\n✅ GENOTYPE PHASING COMPLETED!\n")
            print(message)
        else:
            print("\n❌ Phasing completed but no output files were generated.")
    
    async def run(self, requester_agent: str = "", task_id: str = "") -> List[str]:
        """
        Run the interactive genotype phasing workflow.
        
        Args:
            requester_agent: Name of requesting agent (empty for standalone)
            task_id: Task identifier
            
        Returns:
            List of output file paths
        """
        try:
            # Initialize session
            self._initialize_session(requester_agent, task_id)
            
            # Show welcome and format info
            await self._show_welcome_and_format_info()
            
            # Interactive user input loop
            while True:
                user_input = await self._get_user_input()
                action = await self._handle_user_input(user_input)
                
                if action == "ready":
                    # User is ready, proceed with workchain
                    self.state_manager.transition(PhasingState.WAITING_USER_READY)
                    output_files = await self._execute_workchain()
                    
                    if output_files:
                        self._display_completion_message(output_files)
                        return output_files
                    else:
                        print("\n❌ Phasing failed - no output files generated.")
                        return []
                        
                    
                elif action == "not_ready":
                    # User cancelled
                    print(PHASING_PROMPTS["cancel_message"])
                    self.state_manager.transition(PhasingState.COMPLETED)
                    return []
                    
                elif action == "other_types":
                    # User needs file conversion
                    conversion_success = await self._handle_file_conversion()
                    if conversion_success:
                        # After file conversion, ask again
                        print("\nFile conversion completed. Please confirm if you're now ready:")
                        print(PHASING_PROMPTS["ready_prompt"])
                        continue
                    else:
                        print("\n❌ File conversion failed.")
                        return []
                    
                # action == "invalid" - continue loop to ask again
            
        except Exception as e:
            logger.error(f"Workflow execution failed: {e}")
            print(f"\n❌ Error: {e}")
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
        print("\n=== Genotype Phasing Agent ===")
        
        try:
            output_files = await self.run(requester_agent, task_id)
            
            if output_files:
                print(f"\n✅ Phasing completed successfully!")
                print(f"Generated {len(output_files)} output files.")
            else:
                print("\n❌ Phasing was cancelled or failed.")
            
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
def create_genotype_phasing_agent(supervisor_handoff_callback: Optional[Callable] = None) -> GenotypePhasingAgent:
    """
    Create a genotype phasing agent instance.
    
    Args:
        supervisor_handoff_callback: Callback for supervisor handoff
        
    Returns:
        GenotypePhasingAgent instance
    """
    return GenotypePhasingAgent(supervisor_handoff_callback=supervisor_handoff_callback)