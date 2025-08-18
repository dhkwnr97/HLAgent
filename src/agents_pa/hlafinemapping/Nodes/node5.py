"""
Node5: Meta Analysis from 2+ HLA Binary Marker Panels
Performs meta analysis across multiple phenotypes (requires 2+ datasets).
"""
import asyncio
from typing import List

from ..models import HLAFineMappingState, NodeType
from ..dependencies import HLAFineMappingDependencies
from src.core.workchain_pa import execute_workchain_pa
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Node5 execution state
node5_state = {
    "stage": "start",  # start -> step1 -> step2 -> complete
    "node5_myoutputfile": []
}

async def execute_node5(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Start Node5 execution"""
    global node5_state
    node5_state["stage"] = "start"
    node5_state["node5_myoutputfile"] = []
    
    # Update global state to track node execution
    global_state.update_node_state(NodeType.NODE5, "in_progress")
    
    logger.info("Starting Node5: Meta analysis from 2+ HLA binary marker panels")
    
    return """📈 **Node5: Meta Analysis Started**

Node5 performs meta analysis across multiple phenotypes. This is used when you have 2 or more different phenotypes (e.g., RA and CD).

**Requirements:**
- 2+ `.phe` files (different phenotypes)
- Binary marker panels from Node1
- Regression outputs from Node2 (`.assoc.logistic` or `.assoc.linear` files)

**Example use case:** Meta analysis across Rheumatoid Arthritis (RA) and Crohn's Disease (CD) datasets.

**Do you have the required files ready?** (Please respond "Yes" or "No")
- **Yes**: Continue with Node5 execution
- **No**: Return to workflow customization"""

async def handle_node5_interaction(user_input: str, deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Handle user interactions during Node5 execution"""
    global node5_state
    user_input = user_input.strip().lower()
    
    if node5_state["stage"] == "start":
        if user_input == "yes":
            node5_state["stage"] = "step1"
            return await execute_node5_step1(deps, global_state)
        elif user_input == "no":
            # Return to workflow customization
            from ..agent import state
            state.stage = global_state.WorkflowStage.WORKFLOW_CUSTOMIZE
            global_state.update_node_state(NodeType.NODE5, "failed", error_message="Required files not available")
            return """**Returning to workflow customization.**

Please describe your desired workflow again when you have the required files ready."""
        else:
            return """Please respond with **"Yes"** if you have the required files or **"No"** to return to workflow customization."""
    
    # Should not reach here in normal flow
    return "❌ **Error:** Unexpected state in Node5 execution."

async def execute_node5_step1(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Execute Node5 Step 1: metaanal workflow"""
    global node5_state
    
    try:
        logger.info("Node5 Step 1: Executing metaanal workflow")
        
        # Execute metaanal using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("metaanal"),
            python_script_path=deps.get_tool_script_path("metaanal"),
            output_file_prefixes=[],
            output_file_suffixes=[".meta", "_summary.txt"]
        )
        
        # Add to node5 output files
        node5_state["node5_myoutputfile"].extend(output_files)
        
        # Inform user about step 1 completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        
        logger.info(f"Node5 Step 1 completed, generated {len(output_files)} files")
        
        # Continue to step 2
        node5_state["stage"] = "step2"
        return await execute_node5_step2(deps, global_state, step1_message=f"""✅ **Node5 Step 1 Complete: metaanal**

**Generated files:**
{output_list}

**Continuing to Step 2...**

""")
        
    except Exception as e:
        logger.error(f"Node5 Step 1 failed: {e}")
        global_state.update_node_state(NodeType.NODE5, "failed", error_message=str(e))
        return f"❌ **Node5 Step 1 failed:** {str(e)}\n\nReturning to workflow customization."

async def execute_node5_step2(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState, step1_message: str = "") -> str:
    """Execute Node5 Step 2: metaanalPlot workflow"""
    global node5_state
    
    try:
        logger.info("Node5 Step 2: Executing metaanalPlot workflow")
        
        # Execute metaanalPlot using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("metaanalPlot"),
            python_script_path=deps.get_tool_script_path("metaanalPlot"),
            output_file_prefixes=[],
            output_file_suffixes=[".png"]
        )
        
        # Add to node5 output files
        node5_state["node5_myoutputfile"].extend(output_files)
        
        # Complete Node5
        node5_state["stage"] = "complete"
        
        # Add all node5 files to global output
        global_state.add_output_files(node5_state["node5_myoutputfile"])
        global_state.update_node_state(NodeType.NODE5, "completed", node5_state["node5_myoutputfile"])
        
        # Inform user about completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        all_outputs = "\n".join([f"- {file}" for file in node5_state["node5_myoutputfile"]])
        
        logger.info(f"Node5 completed successfully, total {len(node5_state['node5_myoutputfile'])} files generated")
        
        # Complete Node5 and continue workflow
        completion_message = step1_message + f"""✅ **Node5 Step 2 Complete: metaanalPlot**

**Generated files:**
{output_list}

🎉 **Node5 Complete!**

**All Node5 output files:**
{all_outputs}

**Node5 execution finished. Workflow will continue with next node.**

"""
        
        return completion_message
        
    except Exception as e:
        logger.error(f"Node5 Step 2 failed: {e}")
        global_state.update_node_state(NodeType.NODE5, "failed", error_message=str(e))
        return f"❌ **Node5 Step 2 failed:** {str(e)}\n\nReturning to workflow customization."