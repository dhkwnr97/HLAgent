"""
Node1: HLA Binary Marker Panel Creation
Essential first step for HLA fine mapping - creates binary marker panels from reference data.
"""
import asyncio
from typing import List

from ..models import HLAFineMappingState, NodeType
from ..dependencies import HLAFineMappingDependencies
from src.core.workchain_pa import execute_workchain_pa
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Node1 execution state
node1_state = {
    "stage": "start",  # start -> step1 -> step2 -> step3 -> complete
    "node1_myoutputfile": []
}

async def execute_node1(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Start Node1 execution"""
    global node1_state
    node1_state["stage"] = "start"
    node1_state["node1_myoutputfile"] = []
    
    # Update global state to track node execution
    global_state.update_node_state(NodeType.NODE1, "in_progress")
    
    logger.info("Starting Node1: HLA binary marker panel creation")
    
    return """🔬 **Node1: HLA Binary Marker Panel Creation Started**

Node1 creates HLA binary marker panels - this is an essential step for first-time users.

**Requirements:**
- Reference panel data
- `.hped` file (HLA imputation output from CookHLA)

**Do you have the required files ready?** (Please respond "Yes" or "No")
- **Yes**: Continue with Node1 execution
- **No**: Return to workflow customization"""

async def handle_node1_interaction(user_input: str, deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Handle user interactions during Node1 execution"""
    global node1_state
    user_input = user_input.strip().lower()
    
    if node1_state["stage"] == "start":
        if user_input == "yes":
            node1_state["stage"] = "step1"
            return await execute_node1_step1(deps, global_state)
        elif user_input == "no":
            # Return to workflow customization
            from ..agent import state
            state.stage = global_state.WorkflowStage.WORKFLOW_CUSTOMIZE
            global_state.update_node_state(NodeType.NODE1, "failed", error_message="Required files not available")
            return """**Returning to workflow customization.**

Please describe your desired workflow again when you have the required files ready."""
        else:
            return """Please respond with **"Yes"** if you have the required files or **"No"** to return to workflow customization."""
    
    # Should not reach here in normal flow
    return "❌ **Error:** Unexpected state in Node1 execution."

async def execute_node1_step1(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Execute Node1 Step 1: imgt2seq workflow"""
    global node1_state
    
    try:
        logger.info("Node1 Step 1: Executing imgt2seq workflow")
        
        # Execute imgt2seq using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("imgt2seq"),
            python_script_path=deps.get_tool_script_path("imgt2seq"),
            output_file_prefixes=["HLA_DICTIONARY_AA", "HLA_DICTIONARY_SNPS"],
            output_file_suffixes=[".hat"]
        )
        
        # Add to node1 output files
        node1_state["node1_myoutputfile"].extend(output_files)
        
        # Inform user about step 1 completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        
        logger.info(f"Node1 Step 1 completed, generated {len(output_files)} files")
        
        # Continue to step 2
        node1_state["stage"] = "step2"
        return await execute_node1_step2(deps, global_state, step1_message=f"""✅ **Node1 Step 1 Complete: imgt2seq**

**Generated files:**
{output_list}

**Continuing to Step 2...**

""")
        
    except Exception as e:
        logger.error(f"Node1 Step 1 failed: {e}")
        global_state.update_node_state(NodeType.NODE1, "failed", error_message=str(e))
        return f"❌ **Node1 Step 1 failed:** {str(e)}\n\nReturning to workflow customization."

async def execute_node1_step2(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState, step1_message: str = "") -> str:
    """Execute Node1 Step 2: nomencleaner workflow"""
    global node1_state
    
    try:
        logger.info("Node1 Step 2: Executing nomencleaner workflow")
        
        # Execute nomencleaner using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("nomencleaner"),
            python_script_path=deps.get_tool_script_path("nomencleaner"),
            output_file_prefixes=[],
            output_file_suffixes=[".chped"]
        )
        
        # Add to node1 output files
        node1_state["node1_myoutputfile"].extend(output_files)
        
        # Inform user about step 2 completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        
        logger.info(f"Node1 Step 2 completed, generated {len(output_files)} files")
        
        # Continue to step 3
        node1_state["stage"] = "step3"
        return await execute_node1_step3(deps, global_state, 
                                       previous_message=step1_message + f"""✅ **Node1 Step 2 Complete: nomencleaner**

**Generated files:**
{output_list}

**Continuing to Step 3...**

""")
        
    except Exception as e:
        logger.error(f"Node1 Step 2 failed: {e}")
        global_state.update_node_state(NodeType.NODE1, "failed", error_message=str(e))
        return f"❌ **Node1 Step 2 failed:** {str(e)}\n\nReturning to workflow customization."

async def execute_node1_step3(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState, previous_message: str = "") -> str:
    """Execute Node1 Step 3: bmarkergenerator workflow"""
    global node1_state
    
    try:
        logger.info("Node1 Step 3: Executing bmarkergenerator workflow")
        
        # Execute bmarkergenerator using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("bmarkergenerator"),
            python_script_path=deps.get_tool_script_path("bmarkergenerator"),
            output_file_prefixes=[],
            output_file_suffixes=[".bed", ".bim", ".fam"]
        )
        
        # Add to node1 output files
        node1_state["node1_myoutputfile"].extend(output_files)
        
        # Complete Node1
        node1_state["stage"] = "complete"
        
        # Add all node1 files to global output
        global_state.add_output_files(node1_state["node1_myoutputfile"])
        global_state.update_node_state(NodeType.NODE1, "completed", node1_state["node1_myoutputfile"])
        
        # Inform user about completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        all_outputs = "\n".join([f"- {file}" for file in node1_state["node1_myoutputfile"]])
        
        logger.info(f"Node1 completed successfully, total {len(node1_state['node1_myoutputfile'])} files generated")
        
        # Complete Node1 and continue workflow
        completion_message = previous_message + f"""✅ **Node1 Step 3 Complete: bmarkergenerator**

**Generated files:**
{output_list}

🎉 **Node1 Complete!**

**All Node1 output files:**
{all_outputs}

**Node1 execution finished. Workflow will continue with next node.**

"""
        
        return completion_message
        
    except Exception as e:
        logger.error(f"Node1 Step 3 failed: {e}")
        global_state.update_node_state(NodeType.NODE1, "failed", error_message=str(e))
        return f"❌ **Node1 Step 3 failed:** {str(e)}\n\nReturning to workflow customization."