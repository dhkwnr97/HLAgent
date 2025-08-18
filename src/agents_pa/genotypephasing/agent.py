"""
Genotype Phasing Agent
Professional genotype phasing using Beagle tools with PydanticAI integration.
"""

import os
from dotenv import load_dotenv
import asyncio

# Fix for event loop issues with Gemini models
from src.utils.event_loop_fix import apply_event_loop_fix
apply_event_loop_fix()

from pydantic_ai import Agent

from .models import FileReadyStatus, GenotypePhasingState
from .dependencies import GenotypePhasingDependencies, GenotypePhasingSession
from .prompts import (
    FILE_READINESS_SYSTEM_PROMPT, 
    WELCOME_MESSAGE, 
    OTHER_TYPES_MESSAGE,
    COMPLETION_MESSAGE_TEMPLATE
)
from .tools import (
    execute_genotype_phasing_workflow,
    format_output_files_message
)
from src.agents_pa.shared.universal_providers import get_genotypephasing_model
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

# Fresh agent creation function to prevent event loop issues
def get_fresh_file_readiness_agent():
    """Create a fresh file readiness agent to prevent event loop binding issues."""
    return Agent(
        get_genotypephasing_model(),
        result_type=FileReadyStatus,
        system_prompt=FILE_READINESS_SYSTEM_PROMPT
    )

# Fallback global agent for compatibility
file_readiness_agent = None

# Global state for session management
session_state = GenotypePhasingState()


async def simple_chat(user_input: str, session: GenotypePhasingSession = None) -> str:
    """
    Main chat function handling the genotype phasing workflow.
    
    Args:
        user_input: User's input message
        session: GenotypePhasingSession instance
        
    Returns:
        Response message
    """
    global session_state
    user_input = user_input.strip()
    
    logger.info(f"Processing input '{user_input}' in stage '{session_state.stage}'")
    
    # Handle Done! at any stage first
    if user_input.lower() == "done!":
        session_state.reset()
        return "🎉 **Genotype Phasing session complete!** Returning to Supervisor. Goodbye!"
    
    # If user says "ready", "not ready", or "other types", handle them regardless of stage
    # This provides a more robust Streamlit experience
    if user_input.lower() == "ready":
        return await execute_continue_point_1(session)
    elif user_input.lower() == "not ready":
        session_state.reset()
        return "👋 **Session ended.** Returning to Supervisor agent. Feel free to come back when you're ready!"
    elif user_input.lower() == "other types":
        return await handle_other_types(session)
    
    # WELCOME STAGE
    if session_state.stage == "welcome":
        if user_input.lower() == "start" or "welcome" in user_input.lower():
            session_state.stage = "readiness_check"
            return WELCOME_MESSAGE
    
    # READINESS CHECK STAGE
    elif session_state.stage == "readiness_check":
        # For non-exact matches, use LLM-based processing for non-standard inputs
        try:
            logger.info(f"Using LLM to interpret user input: {user_input}")
            # Create fresh agent to prevent event loop issues
            fresh_agent = get_fresh_file_readiness_agent()
            result = await fresh_agent.run(user_input)
            status = result.data.status.lower()
            
            if status == "ready":
                return await execute_continue_point_1(session)
            elif status == "not_ready":
                session_state.reset()
                return "👋 **Session ended.** Returning to Supervisor agent. Feel free to come back when you're ready!"
            elif status == "other_types":
                return await handle_other_types(session)
            else:
                return """❌ **Invalid input detected.**

Please provide a valid response:
- **"ready"** - You have files in supported formats (.vcf, .bgl/.markers, .bed/.bim/.fam)
- **"not ready"** - You're not ready to proceed
- **"other types"** - Your files need format conversion first

What's your status?"""
                
        except Exception as e:
            logger.error(f"LLM processing failed: {str(e)}")
            return """❌ **Invalid input detected.**

Please provide a valid response:
- **"ready"** - You have files in supported formats (.vcf, .bgl/.markers, .bed/.bim/.fam)  
- **"not ready"** - You're not ready to proceed
- **"other types"** - Your files need format conversion first

What's your status?"""
    
    # DONE STAGE - FINAL STAGE
    elif session_state.stage == "done":
        if user_input.lower() == "done!":
            session_state.reset()
            return "🎉 **Genotype Phasing session complete!** Returning to Supervisor. Goodbye!"
        elif user_input.lower() == "continue":
            session_state.stage = "readiness_check"
            return """🔄 **Ready for another phasing operation!**

Please let me know your file readiness status:
- Type **"ready"** if you have files in supported formats
- Type **"not ready"** if you're not ready to proceed  
- Type **"other types"** if your files need format conversion first

What's your status?"""
        else:
            return f"""Please choose your next action:

**Current Output Files:**
{format_output_files_message(session_state.myoutputfile)}

**Options:**
- Type **'Done!'** to finish and return to Supervisor
- Type **'continue'** to perform more phasing operations

What would you like to do?"""
    
    return "I don't understand. Please follow the instructions provided."


async def execute_continue_point_1(session: GenotypePhasingSession = None) -> str:
    """Execute the main genotype phasing workflow (continue_point_1)"""
    try:
        logger.info("Executing continue_point_1 - genotype phasing workflow")
        
        # Create dependencies if session not provided
        if session is None:
            deps = GenotypePhasingDependencies.create_default(
                session_id=f"genotype_phasing_{hash(str(session_state))}"
            )
            session = GenotypePhasingSession(deps)
        
        # Execute genotype phasing using workchain_pa
        from src.core.workchain_pa import execute_workchain_pa
        
        wc_result = await execute_workchain_pa(
            orig_yaml_file=session.get_phasing_config_path(),
            python_script_path=session.get_phasing_script_path(),
            output_file_prefixes=[],
            output_file_suffixes=[".aa", ".phased", ".bgl", ".markers"]
        )
        
        if wc_result:
            # Add output files to both session and global state
            session.add_output_files(wc_result)
            session_state.myoutputfile.extend(wc_result)
            session_state.stage = "done"
            
            # Format file list for display
            file_list = format_output_files_message(wc_result)
            
            return COMPLETION_MESSAGE_TEMPLATE.format(file_list=file_list)
        else:
            return "❌ **Error:** Genotype phasing failed - no output files were generated. Please check your input files and try again."
            
    except Exception as e:
        error_msg = f"❌ **Error:** {str(e)}"
        logger.error(f"Error in continue_point_1: {str(e)}")
        return error_msg


async def handle_other_types(session: GenotypePhasingSession = None) -> str:
    """Handle 'other types' workflow - provide guidance and return to supervisor"""
    try:
        logger.info("Handling 'other types' - providing guidance and returning to supervisor")
        
        # Reset session state since we're ending this session
        global session_state
        session_state.reset()
        
        # Return guidance message
        return OTHER_TYPES_MESSAGE
        
    except Exception as e:
        error_msg = f"Error handling other types request: {str(e)}"
        logger.error(error_msg)
        return f"❌ {error_msg}\n\nPlease ask the Supervisor to connect you with the File Converter agent."


class GenotypePhasingAgentPA:
    """Main Genotype Phasing Agent class for handover compatibility"""
    
    def __init__(self):
        self.session = None
    
    async def initialize(self, deps: GenotypePhasingDependencies):
        """Initialize agent with dependencies"""
        logger.info(f"Initializing Genotype Phasing agent for session: {deps.session_id}")
        self.session = GenotypePhasingSession(deps)
        
        # Use a more robust session identifier
        session_identifier = deps.session_id or f"default_{id(deps)}"
        
        # Only reset global state if this is a truly new session
        global session_state
        if not hasattr(session_state, 'current_session_id') or session_state.current_session_id != session_identifier:
            session_state.reset()
            session_state.current_session_id = session_identifier
            logger.info(f"Reset state for new session: {session_identifier}")
        else:
            logger.info(f"Preserving state for existing session: {session_identifier}")
        
        logger.info("Genotype Phasing agent initialized successfully")
    
    async def run(self, user_input: str, deps: GenotypePhasingDependencies) -> str:
        """Run agent with user input"""
        logger.info(f"Genotype phasing processing query: '{user_input}'")
        
        if self.session is None:
            await self.initialize(deps)
        
        # Handle welcome message requests - but also set proper stage
        if user_input == "Please show the welcome message and available options":
            global session_state
            session_state.stage = "readiness_check"  # Set to readiness_check so subsequent inputs work
            return WELCOME_MESSAGE
        
        return await simple_chat(user_input, self.session)
    
    async def chat_loop(self, deps: GenotypePhasingDependencies, standalone=True):
        """Interactive chat loop for standalone usage"""
        if standalone:
            print("Genotype Phasing Agent interactive mode - type 'Done!' to exit")
        
        conversation_count = 0
        status = "active"
        
        try:
            print(await simple_chat("start", self.session))
            while True:
                user_input = input(">>To genotype phasing agent>> ").strip()
                conversation_count += 1
                
                if user_input.lower() == "done!":
                    status = "completed"
                    break
                    
                response = await simple_chat(user_input, self.session)
                print(f"Genotype Phasing Agent: {response}")
                
        except KeyboardInterrupt:
            status = "interrupted"
        except Exception as e:
            status = f"error: {str(e)}"
        
        return {
            "conversation_count": conversation_count,
            "status": status,
            "phasings_completed": len(session_state.myoutputfile),
            "output_files": session_state.myoutputfile.copy()
        }


# Exports
genotypephasing_agent_pa = GenotypePhasingAgentPA()

# Simple functions for direct use
async def run_genotypephasing_workflow(user_input: str, deps=None):
    """Run genotype phasing workflow directly"""
    if deps is None:
        deps = GenotypePhasingDependencies.create_default(
            session_id=f"genotype_phasing_direct_{hash(user_input)}"
        )
    return await genotypephasing_agent_pa.run(user_input, deps)

async def run_genotypephasing_sync(user_input: str, deps=None):
    """Sync wrapper for genotype phasing workflow"""
    return await run_genotypephasing_workflow(user_input, deps)