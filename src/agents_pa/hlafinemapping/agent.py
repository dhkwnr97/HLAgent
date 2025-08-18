"""
HLA Fine Mapping Agent
PydanticAI agent for customizable HLA fine mapping workflows using HATK toolkit.
"""
import os
from dotenv import load_dotenv
import asyncio
from typing import List, Optional, Dict, Any

# Fix for Gemini event loop issues
from src.utils.event_loop_fix import apply_event_loop_fix
apply_event_loop_fix()

from pydantic_ai import Agent, RunContext
from pydantic import BaseModel

from src.agents_pa.shared.universal_providers import get_hlafinemapping_model
from .models import (
    HLAFineMappingState, WorkflowStage, NodeType, WorkflowConfiguration,
    WorkflowParseRequest, WorkflowParseResponse
)
from .dependencies import HLAFineMappingDependencies
from .prompts import (
    HLAFINEMAPPING_SYSTEM_PROMPT, WORKFLOW_PARSING_PROMPT, WELCOME_MESSAGE,
    WORKFLOW_CONFIRMATION_TEMPLATE, COMPLETION_MESSAGE_TEMPLATE
)
from src.utils.logger import setup_logger

logger = setup_logger(__name__)
load_dotenv()

# Workflow parsing agent - will be initialized on demand to avoid event loop issues
workflow_parser_agent = None

# Global state for session management
state = HLAFineMappingState()

def get_workflow_parser_agent():
    """
    Get or create a fresh workflow parser agent.
    This prevents event loop binding issues by creating a new agent each time.
    """
    return Agent(
        get_hlafinemapping_model(),
        result_type=WorkflowParseResponse,
        system_prompt=WORKFLOW_PARSING_PROMPT
    )

async def hla_fine_mapping_chat(user_input: str, deps: HLAFineMappingDependencies) -> str:
    """Main chat function handling HLA Fine Mapping workflow interactions"""
    global state
    user_input = user_input.strip()
    
    # Handle Done! at any stage
    if user_input.lower() == "done!":
        state.reset()
        return "🎉 **HLA Fine Mapping session complete!** Goodbye!"
    
    # STAGE 1: WELCOME
    if state.stage == WorkflowStage.WELCOME:
        if user_input.lower() == "yes":
            state.stage = WorkflowStage.WORKFLOW_CUSTOMIZE
            return """🔧 **Workflow Customization**

I can execute HLA fine mapping analysis with customizable workflow using these nodes:

**Available Nodes:**
- **Node1**: HLA binary marker panel creation (essential for new users)
- **Node2**: Regression analysis from binary marker panel  
- **Node3**: Stepwise conditional regression
- **Node4**: Omnibus test (requires genotype phasing output .aa file)
- **Node5**: Meta analysis from 2+ datasets

**Examples:**
- "I want node1, then node2, then node3" 
- "Let's do binary marker creation followed by regression analysis"
- "I need node1 -> node2 -> node4 -> node3"

**Instructions:**
- Describe your desired workflow in natural language
- Type **"Done!"** to return to supervisor agent

**What workflow would you like to execute?**"""
        
        elif user_input.lower() == "no":
            state.reset()
            return "**Returning to supervisor agent.** Feel free to ask for help with HLA fine mapping later!"
        
        else:
            return WELCOME_MESSAGE
    
    # STAGE 2: WORKFLOW CUSTOMIZATION  
    elif state.stage == WorkflowStage.WORKFLOW_CUSTOMIZE:
        if user_input.lower() == "done!":
            state.reset()
            return "**Returning to supervisor agent.** Feel free to ask for help with HLA fine mapping later!"
        
        try:
            # Parse workflow using PydanticAI with fresh agent to avoid event loop issues
            try:
                # Create a fresh agent for each parsing request to avoid event loop binding issues
                parser_agent = get_workflow_parser_agent()
                parse_result = await parser_agent.run(user_input)
                parsed_workflow = parse_result.data
            except (RuntimeError, asyncio.InvalidStateError) as e:
                if any(keyword in str(e).lower() for keyword in ["event loop", "different event loop", "bound to a different"]):
                    logger.warning(f"Event loop issue detected, retrying with new agent: {e}")
                    # Create another fresh agent and retry
                    parser_agent = get_workflow_parser_agent()
                    parse_result = await parser_agent.run(user_input)
                    parsed_workflow = parse_result.data
                else:
                    raise
            
            # Update state with parsed workflow
            state.workflow_config.nodes = parsed_workflow.nodes
            state.workflow_config.current_node_index = 0
            state.stage = WorkflowStage.WORKFLOW_CONFIRM
            
            # Create human-readable description
            node_names = [f"Node{node.value[-1]}" for node in parsed_workflow.nodes]
            workflow_sequence = " -> ".join(node_names)
            
            return WORKFLOW_CONFIRMATION_TEMPLATE.format(
                workflow_description=parsed_workflow.description,
                node_sequence=workflow_sequence
            )
            
        except Exception as e:
            logger.error(f"Workflow parsing failed: {e}")
            return f"""❌ **Workflow parsing failed:** {str(e)}

Please try again with a clearer description. Examples:
- "I want node1, then node2, then node3"
- "Let's start with binary marker creation, followed by regression analysis"

**What workflow would you like to execute?**"""
    
    # STAGE 3: WORKFLOW CONFIRMATION
    elif state.stage == WorkflowStage.WORKFLOW_CONFIRM:
        if user_input.lower() == "yes":
            state.stage = WorkflowStage.EXECUTING_NODES
            return await execute_next_node(deps)
        
        elif user_input.lower() == "no":
            state.stage = WorkflowStage.WORKFLOW_CUSTOMIZE
            return """🔧 **Workflow Customization**

Please describe your desired workflow again. Examples:
- "I want node1, then node2, then node3"
- "Let's do binary marker creation followed by regression analysis"

**What workflow would you like to execute?**"""
        
        else:
            return """Please respond with **"Yes"** to confirm the workflow or **"No"** to customize it again."""
    
    # STAGE 4: EXECUTING NODES
    elif state.stage == WorkflowStage.EXECUTING_NODES:
        # This stage handles node execution - user responses are passed to individual nodes
        return await handle_node_execution(user_input, deps)
    
    # STAGE 5: FINISHED
    elif state.stage == WorkflowStage.FINISHED:
        if user_input.lower() == "done!":
            state.reset()
            return "🎉 **HLA Fine Mapping session complete!** Returning to supervisor agent."
        
        elif user_input.lower() == "continue":
            state.reset()
            state.stage = WorkflowStage.WELCOME
            return WELCOME_MESSAGE
        
        else:
            return """Please choose:
- **"Done!"**: Return to supervisor agent
- **"continue"**: Start a new HLA fine mapping workflow"""
    
    return "I don't understand. Please follow the instructions above."


async def execute_next_node(deps: HLAFineMappingDependencies) -> str:
    """Execute the next node in the workflow"""
    current_node = state.workflow_config.get_current_node()
    
    if current_node is None:
        # All nodes completed
        state.stage = WorkflowStage.FINISHED
        output_files_text = "\n".join([f"- {file}" for file in state.myoutputfile])
        return COMPLETION_MESSAGE_TEMPLATE.format(output_files=output_files_text)
    
    # Import and execute the appropriate node
    if current_node == NodeType.NODE1:
        from .Nodes.node1 import execute_node1
        return await execute_node1(deps, state)
    elif current_node == NodeType.NODE2:
        from .Nodes.node2 import execute_node2  
        return await execute_node2(deps, state)
    elif current_node == NodeType.NODE3:
        from .Nodes.node3 import execute_node3
        return await execute_node3(deps, state)
    elif current_node == NodeType.NODE4:
        from .Nodes.node4 import execute_node4
        return await execute_node4(deps, state)
    elif current_node == NodeType.NODE5:
        from .Nodes.node5 import execute_node5
        return await execute_node5(deps, state)
    else:
        return f"❌ **Error:** Unknown node type: {current_node}"


async def handle_node_execution(user_input: str, deps: HLAFineMappingDependencies) -> str:
    """Handle user input during node execution"""
    current_node = state.workflow_config.get_current_node()
    
    if current_node is None:
        # Should not happen, but handle gracefully
        return await execute_next_node(deps)
    
    # Delegate to appropriate node handler
    if current_node == NodeType.NODE1:
        from .Nodes.node1 import handle_node1_interaction
        response = await handle_node1_interaction(user_input, deps, state)
        # Check if node completed and advance workflow
        if "Node1 execution finished" in response:
            advance_to_next_node()
            next_response = await execute_next_node(deps)
            return response + f"\n\n{next_response}"
        return response
    elif current_node == NodeType.NODE2:
        from .Nodes.node2 import handle_node2_interaction
        response = await handle_node2_interaction(user_input, deps, state)
        if "Node2 execution finished" in response:
            advance_to_next_node() 
            next_response = await execute_next_node(deps)
            return response + f"\n\n{next_response}"
        return response
    elif current_node == NodeType.NODE3:
        from .Nodes.node3 import handle_node3_interaction
        response = await handle_node3_interaction(user_input, deps, state)
        if "Node3 execution finished" in response:
            advance_to_next_node()
            next_response = await execute_next_node(deps)
            return response + f"\n\n{next_response}"
        return response
    elif current_node == NodeType.NODE4:
        from .Nodes.node4 import handle_node4_interaction
        response = await handle_node4_interaction(user_input, deps, state)
        if "Node4 execution finished" in response:
            advance_to_next_node()
            next_response = await execute_next_node(deps)
            return response + f"\n\n{next_response}"
        return response
    elif current_node == NodeType.NODE5:
        from .Nodes.node5 import handle_node5_interaction
        response = await handle_node5_interaction(user_input, deps, state)
        if "Node5 execution finished" in response:
            advance_to_next_node()
            next_response = await execute_next_node(deps)
            return response + f"\n\n{next_response}"
        return response
    else:
        return f"❌ **Error:** Unknown node type: {current_node}"


def advance_to_next_node():
    """Advance workflow to next node"""
    if state.workflow_config.advance_to_next_node():
        return True  # More nodes to execute
    else:
        state.stage = WorkflowStage.FINISHED
        return False  # Workflow complete


# Handover compatibility wrapper
class HLAFineMappingAgentPA:
    """HLA Fine Mapping Agent wrapper for handover compatibility"""
    
    def __init__(self):
        pass
    
    async def initialize(self, deps: HLAFineMappingDependencies):
        """Initialize the HLA Fine Mapping agent"""
        logger.info(f"Initializing HLA Fine Mapping agent for session: {deps.session_id}")
        
        # Use a more robust session identifier
        session_identifier = deps.session_id or f"default_{id(deps)}"
        
        # Only reset global state if this is a truly new session
        global state
        if not hasattr(state, 'current_session_id') or state.current_session_id != session_identifier:
            state.reset()
            state.current_session_id = session_identifier
            logger.info(f"Reset state for new session: {session_identifier}")
        else:
            logger.info(f"Preserving state for existing session: {session_identifier}")
            
        logger.info("HLA Fine Mapping agent initialized successfully")
    
    async def run(self, user_input: str, deps: HLAFineMappingDependencies) -> str:
        """Run HLA Fine Mapping agent with user input"""
        logger.info(f"HLA Fine Mapping agent processing: '{user_input}'")
        
        if user_input == "Please show the welcome message and available analysis options":
            return WELCOME_MESSAGE
        
        # Only return welcome message on initial "start" - not for existing sessions
        if user_input.lower() == "start":
            return WELCOME_MESSAGE
        
        return await hla_fine_mapping_chat(user_input, deps)
    
    async def chat_loop(self, deps: HLAFineMappingDependencies, standalone: bool = True):
        """Interactive chat loop for standalone usage"""
        if standalone:
            print("HLA Fine Mapping Agent interactive mode - type 'Done!' to exit")
        
        conversation_count = 0
        status = "active"
        
        try:
            print(WELCOME_MESSAGE)
            while True:
                user_input = input(">>To hla fine mapping agent>> ").strip()
                conversation_count += 1
                
                if user_input.lower() == "done!":
                    status = "completed"
                    break
                
                response = await hla_fine_mapping_chat(user_input, deps)
                print(f"HLA Fine Mapping: {response}")
                
                if state.stage == WorkflowStage.FINISHED:
                    print("\n**Workflow completed! Type 'Done!' to exit or 'continue' for new workflow.**")
                
        except KeyboardInterrupt:
            status = "interrupted"
        except Exception as e:
            status = f"error: {str(e)}"
        
        return {
            "conversation_count": conversation_count,
            "status": status,
            "nodes_completed": len([s for s in state.node_states if s.status == "completed"]),
            "output_files": state.myoutputfile.copy()
        }


# Export agent instance
hlafinemapping_agent_pa = HLAFineMappingAgentPA()


# Simple functions for direct use
async def run_hlafinemapping_workflow(user_input: str, deps: HLAFineMappingDependencies = None):
    """Run HLA Fine Mapping workflow with user input"""
    if deps is None:
        deps = HLAFineMappingDependencies.create_default("direct_session")
    
    return await hlafinemapping_agent_pa.run(user_input, deps)


async def run_hlafinemapping_sync(user_input: str, deps: HLAFineMappingDependencies = None):
    """Synchronous wrapper for HLA Fine Mapping workflow"""
    return await run_hlafinemapping_workflow(user_input, deps)