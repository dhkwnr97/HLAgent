"""
HLA Imputation Agent
Professional HLA imputation using multiple bioinformatics tools with PydanticAI integration.
"""

import os
from dotenv import load_dotenv
import asyncio

# Fix for event loop issues with Gemini models
from src.utils.event_loop_fix import apply_event_loop_fix
apply_event_loop_fix()

from pydantic_ai import Agent

from .models import FileReadyStatus, HLAImputationState
from .dependencies import HLAImputationDependencies, HLAImputationSession
from .prompts import (
    FILE_READINESS_SYSTEM_PROMPT, 
    WELCOME_MESSAGE_TEMPLATE, 
    OTHER_TYPES_MESSAGE,
    TOOL_SELECTION_MESSAGE,
    COMPLETION_MESSAGE_TEMPLATE
)
from .tools import (
    scan_hla_tools,
    validate_tool_selection,
    execute_hla_imputation_workflow,
    format_tool_list,
    format_file_requirements,
    format_tool_selection_options,
    format_output_files_message,
    get_output_descriptions
)
from src.agents_pa.shared.universal_providers import get_hlaimputation_model
from src.utils.logger import setup_logger

load_dotenv()
logger = setup_logger(__name__)

# Fresh agent creation function to prevent event loop issues
def get_fresh_file_readiness_agent():
    """Create a fresh file readiness agent to prevent event loop binding issues."""
    return Agent(
        get_hlaimputation_model(),
        result_type=FileReadyStatus,
        system_prompt=FILE_READINESS_SYSTEM_PROMPT
    )

# Fallback global agent for compatibility
file_readiness_agent = None

# Global state for session management
session_state = HLAImputationState()


async def simple_chat(user_input: str, session: HLAImputationSession = None) -> str:
    """
    Main chat function handling the HLA imputation workflow.
    
    Args:
        user_input: User's input message
        session: HLAImputationSession instance
        
    Returns:
        Response message
    """
    global session_state
    user_input = user_input.strip()
    
    logger.info(f"Processing input '{user_input}' in stage '{session_state.stage}'")
    
    # Handle Done! at any stage first
    if user_input.lower() == "done!":
        session_state.reset()
        return "🎉 **HLA Imputation session complete!** Returning to Supervisor. Goodbye!"
    
    # If user says "ready", "not ready", or "other types", handle them regardless of stage
    # This provides a more robust Streamlit experience
    if user_input.lower() == "ready":
        return await handle_ready_status(session)
    elif user_input.lower() == "not ready":
        session_state.reset()
        return "👋 **Session ended.** Returning to Supervisor agent. Feel free to come back when you're ready!"
    elif user_input.lower() == "other types":
        return await handle_other_types()
    
    # WELCOME STAGE
    if session_state.stage == "welcome":
        if user_input.lower() == "start" or "welcome" in user_input.lower():
            return await show_welcome_message(session)
    
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
                return await handle_ready_status(session)
            elif status == "not_ready":
                session_state.reset()
                return "👋 **Session ended.** Returning to Supervisor agent. Feel free to come back when you're ready!"
            elif status == "other_types":
                return await handle_other_types()
            else:
                return """❌ **Invalid input detected.**

Please provide a valid response:
- **"ready"** - You have files in the required formats for HLA imputation
- **"not ready"** - You're not ready to proceed
- **"other types"** - Your files need format conversion first

What's your status?"""
                
        except Exception as e:
            logger.error(f"LLM processing failed: {str(e)}")
            return """❌ **Invalid input detected.**

Please provide a valid response:
- **"ready"** - You have files in the required formats for HLA imputation
- **"not ready"** - You're not ready to proceed
- **"other types"** - Your files need format conversion first

What's your status?"""
    
    # TOOL SELECTION STAGE
    elif session_state.stage == "tool_selection":
        return await handle_tool_selection(user_input, session)
    
    # DONE STAGE - FINAL STAGE
    elif session_state.stage == "done":
        if user_input.lower() == "done!":
            session_state.reset()
            return "🎉 **HLA Imputation session complete!** Returning to Supervisor. Goodbye!"
        elif user_input.lower() == "continue":
            session_state.stage = "welcome"
            return await show_welcome_message(session)
        else:
            return f"""Please choose your next action:

**Current Output Files:**
{format_output_files_message(session_state.myoutputfile)}

**Options:**
- Type **'Done!'** to finish and return to Supervisor
- Type **'continue'** to perform more HLA imputation operations

What would you like to do?"""
    
    return "I don't understand. Please follow the instructions provided."


async def show_welcome_message(session: HLAImputationSession = None) -> str:
    """Show welcome message with available tools"""
    try:
        # Create session if not provided
        if session is None:
            deps = HLAImputationDependencies.create_default(
                session_id=f"hla_imputation_{hash(str(session_state))}"
            )
            session = HLAImputationSession(deps)
        
        # Scan available HLA tools
        tools_directory = session.get_hla_tools_directory()
        available_tools = scan_hla_tools(tools_directory)
        
        if not available_tools:
            return "❌ **Error**: No HLA imputation tools found. Please check your installation."
        
        # Store available tools
        tool_names = [tool.name for tool in available_tools]
        session.set_available_tools(tool_names)
        session_state.available_tools = tool_names
        session_state.stage = "readiness_check"
        
        # Format welcome message
        tool_list = format_tool_list(available_tools)
        file_requirements = format_file_requirements(available_tools)
        
        return WELCOME_MESSAGE_TEMPLATE.format(
            tool_list=tool_list,
            file_requirements=file_requirements
        )
        
    except Exception as e:
        error_msg = f"Error showing welcome message: {str(e)}"
        logger.error(error_msg)
        return f"❌ **Error**: {error_msg}"


async def handle_ready_status(session: HLAImputationSession = None) -> str:
    """Handle when user says they're ready"""
    try:
        # Ensure we have available tools
        if not session_state.available_tools:
            return await show_welcome_message(session)
        
        session_state.stage = "tool_selection"
        
        # Show tool selection options
        tool_options = format_tool_selection_options(session_state.available_tools)
        
        return TOOL_SELECTION_MESSAGE.format(tool_options=tool_options)
        
    except Exception as e:
        error_msg = f"Error handling ready status: {str(e)}"
        logger.error(error_msg)
        return f"❌ **Error**: {error_msg}"


async def handle_other_types() -> str:
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


async def handle_tool_selection(user_input: str, session: HLAImputationSession = None) -> str:
    """Handle tool selection workflow"""
    try:
        # Validate tool selection
        selection_result = validate_tool_selection(user_input, session_state.available_tools)
        
        if not selection_result.valid:
            return f"""❌ **{selection_result.error_message}**

Please try again. {TOOL_SELECTION_MESSAGE.format(
    tool_options=format_tool_selection_options(session_state.available_tools)
)}"""
        
        # Execute HLA imputation with selected tool
        selected_tool = selection_result.tool_name
        session_state.selected_tool = selected_tool
        
        if session:
            session.set_selected_tool(selected_tool)
        
        logger.info(f"User selected tool: {selected_tool}")
        
        # Execute HLA imputation workflow
        return await execute_hla_imputation_with_tool(selected_tool, session)
        
    except Exception as e:
        error_msg = f"Error handling tool selection: {str(e)}"
        logger.error(error_msg)
        return f"❌ **Error**: {error_msg}"


async def execute_hla_imputation_with_tool(tool_name: str, session: HLAImputationSession = None) -> str:
    """Execute HLA imputation with selected tool"""
    try:
        logger.info(f"Executing HLA imputation with tool: {tool_name}")
        
        # Create dependencies if session not provided
        if session is None:
            deps = HLAImputationDependencies.create_default(
                session_id=f"hla_imputation_{hash(str(session_state))}"
            )
            session = HLAImputationSession(deps)
        
        # Execute HLA imputation using workchain_pa
        from src.core.workchain_pa import execute_workchain_pa
        
        wc_result = await execute_workchain_pa(
            orig_yaml_file=session.get_tool_config_path(tool_name),
            python_script_path=session.get_tool_script_path(tool_name),
            output_file_prefixes=[],
            output_file_suffixes=[".hped", ".alleles", "_final.result.txt", ".tsv"]
        )
        
        if wc_result:
            # Add output files to both session and global state
            session.add_output_files(wc_result)
            session_state.myoutputfile.extend(wc_result)
            session_state.stage = "done"
            
            # Format completion message
            file_list = format_output_files_message(wc_result)
            output_descriptions = get_output_descriptions(tool_name)
            
            return COMPLETION_MESSAGE_TEMPLATE.format(
                tool_name=tool_name.upper(),
                file_list=file_list,
                output_descriptions=output_descriptions
            )
        else:
            return f"❌ **Error:** HLA imputation with {tool_name} failed - no output files were generated. Please check your input files and try again."
            
    except Exception as e:
        error_msg = f"❌ **Error:** {str(e)}"
        logger.error(f"Error in HLA imputation execution: {str(e)}")
        return error_msg


class HLAImputationAgentPA:
    """Main HLA Imputation Agent class for handover compatibility"""
    
    def __init__(self):
        self.session = None
    
    async def initialize(self, deps: HLAImputationDependencies):
        """Initialize agent with dependencies"""
        logger.info(f"Initializing HLA Imputation agent for session: {deps.session_id}")
        self.session = HLAImputationSession(deps)
        
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
        
        logger.info("HLA Imputation agent initialized successfully")
    
    async def run(self, user_input: str, deps: HLAImputationDependencies) -> str:
        """Run agent with user input"""
        logger.info(f"HLA imputation processing query: '{user_input}'")
        
        if self.session is None:
            await self.initialize(deps)
        
        # Handle welcome message requests - but also set proper stage
        if user_input == "Please show the welcome message and available options":
            return await show_welcome_message(self.session)
        
        return await simple_chat(user_input, self.session)
    
    async def chat_loop(self, deps: HLAImputationDependencies, standalone=True):
        """Interactive chat loop for standalone usage"""
        if standalone:
            print("HLA Imputation Agent interactive mode - type 'Done!' to exit")
        
        conversation_count = 0
        status = "active"
        
        try:
            print(await show_welcome_message(self.session))
            while True:
                user_input = input(">>To hla imputation agent>> ").strip()
                conversation_count += 1
                
                if user_input.lower() == "done!":
                    status = "completed"
                    break
                    
                response = await simple_chat(user_input, self.session)
                print(f"HLA Imputation Agent: {response}")
                
        except KeyboardInterrupt:
            status = "interrupted"
        except Exception as e:
            status = f"error: {str(e)}"
        
        return {
            "conversation_count": conversation_count,
            "status": status,
            "imputations_completed": len(session_state.myoutputfile),
            "output_files": session_state.myoutputfile.copy()
        }


# Exports
hlaimputation_agent_pa = HLAImputationAgentPA()

# Simple functions for direct use
async def run_hlaimputation_workflow(user_input: str, deps=None):
    """Run HLA imputation workflow directly"""
    if deps is None:
        deps = HLAImputationDependencies.create_default(
            session_id=f"hla_imputation_direct_{hash(user_input)}"
        )
    return await hlaimputation_agent_pa.run(user_input, deps)

async def run_hlaimputation_sync(user_input: str, deps=None):
    """Sync wrapper for HLA imputation workflow"""
    return await run_hlaimputation_workflow(user_input, deps)