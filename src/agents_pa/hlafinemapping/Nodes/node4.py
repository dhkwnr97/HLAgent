"""
Node4: Omnibus Test from HLA Binary Marker Panel
Performs omnibus test analysis with meta-analysis plotting.
"""
import asyncio
from typing import List

from ..models import HLAFineMappingState, NodeType
from ..dependencies import HLAFineMappingDependencies
from src.core.workchain_pa import execute_workchain_pa
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Node4 execution state
node4_state = {
    "stage": "start",  # start -> step1 -> step2 -> complete
    "node4_myoutputfile": []
}

async def execute_node4(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Start Node4 execution"""
    global node4_state
    node4_state["stage"] = "start"
    node4_state["node4_myoutputfile"] = []
    
    # Update global state to track node execution
    global_state.update_node_state(NodeType.NODE4, "in_progress")
    
    logger.info("Starting Node4: Omnibus test from HLA binary marker panel")
    
    return """🧪 **Node4: Omnibus Test Started**

Node4 performs omnibus test analysis using HLA binary marker panels (typically from Node1).

**Requirements:**
- Binary marker panel files (`.bed`, `.bim`, `.fam`)
- Phenotype file (`.phe`)
- Genotype phasing output file (`.aa`)

**Note:** You can call the genotype phasing agent from supervisor to generate the `.aa` file if needed.

**Do you have the required files ready?** (Please respond "Yes" or "No")
- **Yes**: Continue with Node4 execution
- **No**: Return to workflow customization"""

async def handle_node4_interaction(user_input: str, deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Handle user interactions during Node4 execution"""
    global node4_state
    user_input = user_input.strip().lower()
    
    if node4_state["stage"] == "start":
        if user_input == "yes":
            node4_state["stage"] = "step1"
            return await execute_node4_step1(deps, global_state)
        elif user_input == "no":
            # Return to workflow customization
            from ..agent import state
            state.stage = global_state.WorkflowStage.WORKFLOW_CUSTOMIZE
            global_state.update_node_state(NodeType.NODE4, "failed", error_message="Required files not available")
            return """**Returning to workflow customization.**

Please describe your desired workflow again when you have the required files ready."""
        else:
            return """Please respond with **"Yes"** if you have the required files or **"No"** to return to workflow customization."""
    
    # Should not reach here in normal flow
    return "❌ **Error:** Unexpected state in Node4 execution."

async def execute_node4_step1(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Execute Node4 Step 1: omnibustest workflow"""
    global node4_state
    
    try:
        logger.info("Node4 Step 1: Executing omnibustest workflow")
        
        # Execute omnibustest using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("omnibustest"),
            python_script_path=deps.get_tool_script_path("omnibustest"),
            output_file_prefixes=[],
            output_file_suffixes=[".omnibus"]
        )
        
        # Add to node4 output files
        node4_state["node4_myoutputfile"].extend(output_files)
        
        # Inform user about step 1 completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        
        logger.info(f"Node4 Step 1 completed, generated {len(output_files)} files")
        
        # Continue to step 2
        node4_state["stage"] = "step2"
        return await execute_node4_step2(deps, global_state, step1_message=f"""✅ **Node4 Step 1 Complete: omnibustest**

**Generated files:**
{output_list}

**Continuing to Step 2...**

""")
        
    except Exception as e:
        logger.error(f"Node4 Step 1 failed: {e}")
        global_state.update_node_state(NodeType.NODE4, "failed", error_message=str(e))
        return f"❌ **Node4 Step 1 failed:** {str(e)}\n\nReturning to workflow customization."

async def execute_node4_step2(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState, step1_message: str = "") -> str:
    """Execute Node4 Step 2: metaanalPlot workflow"""
    global node4_state
    
    try:
        logger.info("Node4 Step 2: Executing metaanalPlot workflow")
        
        # Execute metaanalPlot using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("metaanalPlot"),
            python_script_path=deps.get_tool_script_path("metaanalPlot"),
            output_file_prefixes=[],
            output_file_suffixes=[".html", ".png", ".pdf", ".svg"]
        )
        
        # Add to node4 output files
        node4_state["node4_myoutputfile"].extend(output_files)
        
        # Complete Node4
        node4_state["stage"] = "complete"
        
        # Add all node4 files to global output
        global_state.add_output_files(node4_state["node4_myoutputfile"])
        global_state.update_node_state(NodeType.NODE4, "completed", node4_state["node4_myoutputfile"])
        
        # Inform user about completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        all_outputs = "\n".join([f"- {file}" for file in node4_state["node4_myoutputfile"]])
        
        logger.info(f"Node4 completed successfully, total {len(node4_state['node4_myoutputfile'])} files generated")
        
        # Complete Node4 and continue workflow
        completion_message = step1_message + f"""✅ **Node4 Step 2 Complete: metaanalPlot**

**Generated files:**
{output_list}

🎉 **Node4 Complete!**

**All Node4 output files:**
{all_outputs}

**Node4 execution finished. Workflow will continue with next node.**

"""
        
        return completion_message
        
    except Exception as e:
        logger.error(f"Node4 Step 2 failed: {e}")
        global_state.update_node_state(NodeType.NODE4, "failed", error_message=str(e))
        return f"❌ **Node4 Step 2 failed:** {str(e)}\n\nReturning to workflow customization."