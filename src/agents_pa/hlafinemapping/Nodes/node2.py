"""
Node2: Regression Analysis from HLA Binary Marker Panel
Performs regression analysis using binary marker panels from Node1.
"""
import asyncio
from typing import List

from ..models import HLAFineMappingState, NodeType
from ..dependencies import HLAFineMappingDependencies
from src.core.workchain_pa import execute_workchain_pa
from src.utils.logger import setup_logger

logger = setup_logger(__name__)

# Node2 execution state
node2_state = {
    "stage": "start",  # start -> step1 -> step2 -> step3 -> complete
    "node2_myoutputfile": []
}

async def execute_node2(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Start Node2 execution"""
    global node2_state
    node2_state["stage"] = "start"
    node2_state["node2_myoutputfile"] = []
    
    # Update global state to track node execution
    global_state.update_node_state(NodeType.NODE2, "in_progress")
    
    logger.info("Starting Node2: Regression analysis from HLA binary marker panel")
    
    return """📊 **Node2: Regression Analysis Started**

Node2 performs regression analysis using HLA binary marker panels (typically from Node1).

**Requirements:**
- Binary marker panel files (`.bed`, `.bim`, `.fam`)
- Phenotype file (`.phe`)

**Do you have the required files ready?** (Please respond "Yes" or "No")
- **Yes**: Continue with Node2 execution
- **No**: Return to workflow customization"""

async def handle_node2_interaction(user_input: str, deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Handle user interactions during Node2 execution"""
    global node2_state
    user_input = user_input.strip().lower()
    
    if node2_state["stage"] == "start":
        if user_input == "yes":
            node2_state["stage"] = "step1"
            return await execute_node2_step1(deps, global_state)
        elif user_input == "no":
            # Return to workflow customization
            from ..agent import state
            state.stage = global_state.WorkflowStage.WORKFLOW_CUSTOMIZE
            global_state.update_node_state(NodeType.NODE2, "failed", error_message="Required files not available")
            return """**Returning to workflow customization.**

Please describe your desired workflow again when you have the required files ready."""
        else:
            return """Please respond with **"Yes"** if you have the required files or **"No"** to return to workflow customization."""
    
    # Should not reach here in normal flow
    return "❌ **Error:** Unexpected state in Node2 execution."

async def execute_node2_step1(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState) -> str:
    """Execute Node2 Step 1: bmarkerregression workflow"""
    global node2_state
    
    try:
        logger.info("Node2 Step 1: Executing bmarkerregression workflow")
        
        # Execute bmarkerregression using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("bmarkerregression"),
            python_script_path=deps.get_tool_script_path("bmarkerregression"),
            output_file_prefixes=[],
            output_file_suffixes=[".assoc.logistic", ".assoc.linear"]
        )
        
        # Add to node2 output files
        node2_state["node2_myoutputfile"].extend(output_files)
        
        # Inform user about step 1 completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        
        logger.info(f"Node2 Step 1 completed, generated {len(output_files)} files")
        
        # Continue to step 2
        node2_state["stage"] = "step2"
        return await execute_node2_step2(deps, global_state, step1_message=f"""✅ **Node2 Step 1 Complete: bmarkerregression**

**Generated files:**
{output_list}

**Continuing to Step 2...**

""")
        
    except Exception as e:
        logger.error(f"Node2 Step 1 failed: {e}")
        global_state.update_node_state(NodeType.NODE2, "failed", error_message=str(e))
        return f"❌ **Node2 Step 1 failed:** {str(e)}\n\nReturning to workflow customization."

async def execute_node2_step2(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState, step1_message: str = "") -> str:
    """Execute Node2 Step 2: manhattanPlot workflow"""
    global node2_state
    
    try:
        logger.info("Node2 Step 2: Executing manhattanPlot workflow")
        
        # Execute manhattanPlot using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("manhattanPlot"),
            python_script_path=deps.get_tool_script_path("manhattanPlot"),
            output_file_prefixes=[],
            output_file_suffixes=[".html", ".png", ".pdf", ".svg"]
        )
        
        # Add to node2 output files
        node2_state["node2_myoutputfile"].extend(output_files)
        
        # Inform user about step 2 completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        
        logger.info(f"Node2 Step 2 completed, generated {len(output_files)} files")
        
        # Continue to step 3
        node2_state["stage"] = "step3"
        return await execute_node2_step3(deps, global_state, 
                                       previous_message=step1_message + f"""✅ **Node2 Step 2 Complete: manhattanPlot**

**Generated files:**
{output_list}

**Continuing to Step 3...**

""")
        
    except Exception as e:
        logger.error(f"Node2 Step 2 failed: {e}")
        global_state.update_node_state(NodeType.NODE2, "failed", error_message=str(e))
        return f"❌ **Node2 Step 2 failed:** {str(e)}\n\nReturning to workflow customization."

async def execute_node2_step3(deps: HLAFineMappingDependencies, global_state: HLAFineMappingState, previous_message: str = "") -> str:
    """Execute Node2 Step 3: heatmap workflow"""
    global node2_state
    
    try:
        logger.info("Node2 Step 3: Executing heatmap workflow")
        
        # Execute heatmap using workchain_pa
        output_files = await execute_workchain_pa(
            orig_yaml_file=deps.get_tool_config_path("heatmap"),
            python_script_path=deps.get_tool_script_path("heatmap"),
            output_file_prefixes=[],
            output_file_suffixes=[".html", ".png", ".pdf", ".svg"]
        )
        
        # Add to node2 output files
        node2_state["node2_myoutputfile"].extend(output_files)
        
        # Complete Node2
        node2_state["stage"] = "complete"
        
        # Add all node2 files to global output
        global_state.add_output_files(node2_state["node2_myoutputfile"])
        global_state.update_node_state(NodeType.NODE2, "completed", node2_state["node2_myoutputfile"])
        
        # Inform user about completion
        output_list = "\n".join([f"- {file}" for file in output_files])
        all_outputs = "\n".join([f"- {file}" for file in node2_state["node2_myoutputfile"]])
        
        logger.info(f"Node2 completed successfully, total {len(node2_state['node2_myoutputfile'])} files generated")
        
        # Complete Node2 and continue workflow
        completion_message = previous_message + f"""✅ **Node2 Step 3 Complete: heatmap**

**Generated files:**
{output_list}

🎉 **Node2 Complete!**

**All Node2 output files:**
{all_outputs}

**Node2 execution finished. Workflow will continue with next node.**

"""
        
        return completion_message
        
    except Exception as e:
        logger.error(f"Node2 Step 3 failed: {e}")
        global_state.update_node_state(NodeType.NODE2, "failed", error_message=str(e))
        return f"❌ **Node2 Step 3 failed:** {str(e)}\n\nReturning to workflow customization."