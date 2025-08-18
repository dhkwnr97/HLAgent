"""
Node3: Stepwise Conditional Regression from HLA Binary Marker Panel
Performs stepwise conditional regression analysis using binary marker panels.
"""
import asyncio
from typing import List

from ..models import HLAFineMappingState, NodeType
from ..dependencies import HLAFineMappingDependencies
from src.core.workchain_pa import execute_workchain_pa
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Node3 execution state
node3_state = {
    "stage": "start",  # start -> step1 -> complete
    "node3_myoutputfile": []
}

async def execute_node3(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Start Node3 execution"""
    global node3_state
    node3_state["stage"] = "start"
    node3_state["node3_myoutputfile"] = []
    
    # Update global state to track node execution
    global_state.update_node_state(NodeType.NODE3, "in_progress")
    
    logger.info("Starting Node3: Stepwise conditional regression from HLA binary marker panel")
    
    return """🔍 **Node3: Stepwise Conditional Regression Started**

Node3 performs stepwise conditional regression analysis using HLA binary marker panels (typically from Node1).

**Requirements:**
- Binary marker panel files (`.bed`, `.bim`, `.fam`)
- Phenotype file (`.phe`)

**Do you have the required files ready?** (Please respond "Yes" or "No")
- **Yes**: Continue with Node3 execution
- **No**: Return to workflow customization"""

async def handle_node3_interaction(user_input: str, deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Handle user interactions during Node3 execution"""
    global node3_state
    user_input = user_input.strip().lower()
    
    if node3_state["stage"] == "start":
        if user_input == "yes":
            node3_state["stage"] = "step1"
            return await execute_node3_step1(deps, global_state)
        elif user_input == "no":
            # Return to workflow customization
            from ..agent import state
            state.stage = global_state.WorkflowStage.WORKFLOW_CUSTOMIZE
            global_state.update_node_state(NodeType.NODE3, "failed", error_message="Required files not available")
            return """**Returning to workflow customization.**

Please describe your desired workflow again when you have the required files ready."""
        else:
            return """Please respond with **"Yes"** if you have the required files or **"No"** to return to workflow customization."""
    
    # Should not reach here in normal flow
    return "❌ **Error:** Unexpected state in Node3 execution."

async def execute_node3_step1(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Execute Node3 Step 1: bmarkerstepwiseregression workflow"""
    global node3_state
    
    try:
        logger.info("Node3 Step 1: Executing bmarkerstepwiseregression workflow")
        
        # Execute bmarkerstepwiseregression using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("bmarkerstepwiseregression"),
            python_script_path=deps.get_tool_script_path("bmarkerstepwiseregression"),
            output_file_prefixes=[],
            output_file_suffixes=[".txt", ".json", ".csv"]
        )
        
        # Add to node3 output files
        node3_state["node3_myoutputfile"].extend(output_files)
        
        # Complete Node3
        node3_state["stage"] = "complete"
        
        # Add all node3 files to global output
        global_state.add_output_files(node3_state["node3_myoutputfile"])
        global_state.update_node_state(NodeType.NODE3, "completed", node3_state["node3_myoutputfile"])
        
        # Inform user about completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        
        logger.info(f"Node3 completed successfully, generated {len(output_files)} files")
        
        # Complete Node3 and continue workflow
        completion_message = f"""✅ **Node3 Step 1 Complete: bmarkerstepwiseregression**

**Generated files:**
{output_list}

🎉 **Node3 Complete!**

**All Node3 output files:**
{output_list}

**Node3 execution finished. Workflow will continue with next node.**

"""
        
        return completion_message
        
    except Exception as e:
        logger.error(f"Node3 Step 1 failed: {e}")
        global_state.update_node_state(NodeType.NODE3, "failed", error_message=str(e))
        return f"❌ **Node3 Step 1 failed:** {str(e)}\n\nReturning to workflow customization."