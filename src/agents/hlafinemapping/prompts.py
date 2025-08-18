"""
Prompts for HLA Fine Mapping Agent.

Contains all prompts, messages, and templates used by the agent.
"""

# System prompts
SYSTEM_PROMPT = """You are a professional HLA Fine Mapping Agent specialized in HLA (Human Leukocyte Antigen) fine mapping analysis workflows.

Your role is to:
1. Guide users through HLA fine mapping workflows with 5 customizable nodes
2. Allow users to create custom workflows by selecting and ordering nodes
3. Execute workflows using workchains that integrate with parameter handler and supervisor agents
4. Track and report output files from each workflow step
5. Provide clear guidance and explanations throughout the process

You work with these 5 nodes:
- Node1: HLA binary marker panel creation (required for first-time users)
- Node2: Regression analysis from HLA binary marker panel  
- Node3: Stepwise conditional regression from HLA binary marker panel
- Node4: Omnibus test from HLA binary marker panel
- Node5: Meta analysis from over 2 HLA binary marker panels

You operate in a chatting loop with users, allowing them to:
- Customize workflows by selecting nodes (e.g., "node1, node3, node2")
- Execute the customized workflow
- Continue with additional workflows or finish

Always be helpful, professional, and provide clear guidance about file requirements and workflow dependencies."""

# Welcome messages
WELCOME_MESSAGE = """
🧬 === HLA Fine Mapping Agent ===

Welcome to the advanced HLA Fine Mapping analysis system! 

This agent provides 5 specialized nodes for comprehensive HLA fine mapping analysis:

🔸 Node1: HLA Binary Marker Panel Creation** 
- Creates HLA binary marker panels through IMGT2SEQ, Nomencleaner, and Binary Marker Generator
- ⚠️ **Required for first-time users** - Essential foundation step
- Generates: .hat, .chped, .bed, .bim, .fam files

🔸 Node2: Regression Analysis**
- Performs regression analysis from HLA binary marker panel
- Generates association results and visualization plots
- Outputs: .assoc.logistic/.linear, .html, .png, .pdf, .svg files

🔸 Node3: Stepwise Conditional Regression**
- Performs stepwise conditional regression analysis
- Identifies independent association signals
- Outputs: .txt, .json, .csv files

🔸 Node4: Omnibus Test**
- Performs omnibus test analysis (requires genotype phasing)
- Tests overall association across HLA region
- Outputs: .omnibus, .html, .png, .pdf, .svg files

🔸 Node5: Meta Analysis**
- Performs meta-analysis across multiple datasets
- Requires 2+ .assoc.logistic/.linear files from different datasets
- Outputs: .meta, _summary.txt, .png files

You can customize your workflow by selecting and ordering nodes according to your analysis needs.

To begin, I need to check if you have the required input files ready.
"""

SUPERVISOR_WELCOME_MESSAGE = """
🧬 === HLA Fine Mapping Agent (via {requester}) ===

HLA Fine Mapping analysis requested by: {requester}

This agent provides 5 specialized nodes for comprehensive HLA fine mapping analysis:

🔸 Node1: HLA Binary Marker Panel Creation** 
- Creates HLA binary marker panels through IMGT2SEQ, Nomencleaner, and Binary Marker Generator
- ⚠️ **Required for first-time users** - Essential foundation step
- Generates: .hat, .chped, .bed, .bim, .fam files

🔸 Node2: Regression Analysis**
- Performs regression analysis from HLA binary marker panel
- Generates association results and visualization plots
- Outputs: .assoc.logistic/.linear, .html, .png, .pdf, .svg files

🔸 Node3: Stepwise Conditional Regression**
- Performs stepwise conditional regression analysis
- Identifies independent association signals
- Outputs: .txt, .json, .csv files

🔸 Node4: Omnibus Test**
- Performs omnibus test analysis (requires genotype phasing)
- Tests overall association across HLA region
- Outputs: .omnibus, .html, .png, .pdf, .svg files

🔸 Node5: Meta Analysis**
- Performs meta-analysis across multiple datasets
- Requires 2+ .assoc.logistic/.linear files from different datasets
- Outputs: .meta, _summary.txt, .png files


You can customize your workflow by selecting and ordering nodes according to your analysis needs.
"""

# File readiness messages
FILE_REQUIREMENTS_MESSAGE = """
📋 **Required Input Files for HLA Fine Mapping:**

For HLA fine mapping analysis, you need:
".hped" file - HLA imputation results (hla imputation agent output or using file converter agent output)
".phe" file - Phenotype data with case/control information

Do you have these files ready?

**Please respond with:**
- Chat: "ready" - If you have both .hped and .phe files prepared
- Chat: "not ready" - If you need to prepare these files first
"""

NOT_READY_MESSAGE = """
📚 **Preparing Files for HLA Fine Mapping**

For HLA fine mapping analysis, you need HLA imputation results first.

**Recommendation:**
I recommend using the **HLA Imputation Agent** to generate the required .hped files.
The **CookHLA** method is the default and recommended approach for HLA imputation.

Once you have completed HLA imputation and have your .hped and .phe files ready, you can return to this agent.

**Next Steps:**
1. Use HLA Imputation Agent to generate .hped files
2. Prepare your .phe phenotype file
3. Return here when ready

🔄 **HLA Fine Mapping Agent finished.**
"""

# Node explanation messages
NODE_EXPLANATION_MESSAGE = """
🔧 How to customize your workflow:
Enter the nodes you want to execute in order, separated by commas.

**Examples:**
- Chat: "node1, node2" - Basic workflow for first-time users
- Chat: "node2, node3" - Analysis workflow (if Node1 was run before)
- Chat: "node1, node2, node4" - Comprehensive analysis with omnibus test
- Chat: "node5" - Meta-analysis only (requires previous results)

Please enter your desired workflow:
"""

# Workflow execution messages
WORKFLOW_CONSTRUCTION_MESSAGE = """
⚙️ Workflow Construction Complete

**Selected Workflow:** {workflow_sequence}

**Execution Plan:**
{execution_plan}

**Estimated Steps:** {total_steps}

Starting workflow execution...
"""

WORKFLOW_EXECUTION_START = """
🚀 Starting Workflow Execution

**Workflow:** {workflow_sequence}
**Total Nodes:** {total_nodes}

Beginning execution of your customized HLA fine mapping workflow...
"""

NODE_EXECUTION_START = """
🔄 Executing {node_name}

**Description:** {node_description}

{node_specific_message}

Processing...
"""

NODE_EXECUTION_COMPLETE = """
✅ {node_name} Completed Successfully

**Generated Files:**
{output_files}

**Status:** Node execution completed
**Next:** {next_action}
"""

WORKFLOW_PAUSE_MESSAGE = """
⏸️ Workflow Paused

**Current Node:** {current_node}
**Pause Reason:** {pause_reason}

**Action Required:** {pause_action}

The workflow will resume automatically after the required action is completed.
"""

WORKFLOW_RESUME_MESSAGE = """
▶️ Workflow Resumed

**Resuming Node:** {current_node}
**Resume Point:** {resume_point}

Continuing with workflow execution...
"""

# Node-specific messages
NODE1_START_MESSAGE = """
**Node1 Requirements:**
- First-time HLA fine mapping users should run this node
- Creates essential HLA binary marker panels
- Includes 3 sub-steps: IMGT2SEQ → Nomencleaner → Binary Marker Generator
"""

NODE2_START_MESSAGE = """
**Node2 Requirements:**
- Requires HLA binary marker panel (from Node1)
- Performs regression analysis and generates visualization plots
"""

NODE3_START_MESSAGE = """
**Node3 Requirements:**
- Requires HLA binary marker panel (from Node1)
- Performs stepwise conditional regression analysis
"""

NODE4_START_MESSAGE = """
**Node4 Requirements:**
- Requires HLA binary marker panel (from Node1)
- **Genotype phasing required** - will automatically request genotype phasing
- Requires .aa, .phe, .fam files for omnibus test
"""

NODE4_PHASING_MESSAGE = """
**Genotype Phasing Required for Node4**

The omnibus test requires genotype phasing. I will now request genotype phasing via the supervisor agent.

Please wait while genotype phasing is completed...
"""

NODE5_START_MESSAGE = """
**Node5 Requirements:**
- Requires 2+ .assoc.logistic or .assoc.linear files from different .phe datasets
- These files should be generated from Node2 runs on different phenotype datasets
- Performs meta-analysis across multiple datasets
"""

# Completion messages
WORKFLOW_COMPLETE_MESSAGE = """
🎉 Workflow Execution Completed!

**Executed Nodes:** {executed_nodes}
**Total Output Files:** {total_files}

**Generated Output Files:**
{output_files_list}

**Summary:**
{workflow_summary}

All files have been saved to the output directory.

**What's next?**
- Type "continue" to run another workflow
- Type "Done!" to finish HLA fine mapping analysis
"""

CONTINUE_PROMPT_MESSAGE = """
🔄 Continue HLA Fine Mapping Analysis?

Your workflow has been completed successfully. You can now:

**Options:**
- "continue" - Start a new workflow with different nodes
- "Done!" - Finish HLA fine mapping analysis

**What would you like to do?**
"""

AGENT_FINISHED_MESSAGE = """
✅ HLA Fine Mapping Agent Completed

Thank you for using the HLA Fine Mapping Agent!

**Session Summary:**
- Total workflows executed: {total_workflows}
- Total output files generated: {total_files}
- Session duration: {session_duration}

All analysis results have been saved to the output directory.

{completion_context}

Goodbye! 🧬
"""

# Error messages
ERROR_INVALID_NODES = """
❌ Invalid Node Selection

**Invalid nodes:** {invalid_nodes}

**Valid nodes are:** node1, node2, node3, node4, node5

Please enter a valid node selection (e.g., "node1, node2, node3").
"""

ERROR_MISSING_DEPENDENCIES = """
❌ Missing Dependencies

**Missing dependencies:** {missing_dependencies}

**Recommendation:** {recommendation}

Please include the required dependencies in your workflow.
"""

ERROR_WORKFLOW_EXECUTION = """
❌ Workflow Execution Error

**Error in:** {error_location}
**Error message:** {error_message}

**Possible solutions:**
{solutions}

Please check your input files and try again.
"""

ERROR_FILE_NOT_FOUND = """
❌ Required Files Not Found

**Missing files:** {missing_files}

Please ensure all required files are in the correct location and try again.
"""

# Help messages
HELP_MESSAGE = """
📖 HLA Fine Mapping Agent Help

**Available Commands:**
- "ready" - Indicate you have required .hped and .phe files
- "not ready" - Get guidance on preparing files
- "node1, node2, ..." - Select workflow nodes
- "continue" - Run another workflow after completion
- "Done!" - Finish agent session

**Workflow Examples:**
- `node1, node2` - Basic analysis for first-time users
- `node2, node3` - Advanced analysis (if Node1 completed before)
- `node1, node2, node4` - Full analysis with omnibus test
- `node5` - Meta-analysis across datasets

**Node Descriptions:**
- Node1: HLA binary marker panel creation
- Node2: Regression analysis and visualization
- Node3: Stepwise conditional regression
- Node4: Omnibus test (requires genotype phasing)
- Node5: Meta-analysis across multiple datasets

Need more help? Ask specific questions about nodes or workflows!
"""

# Validation messages
VALIDATION_SUCCESS = """
✅ Input Validation Successful

All required files are ready for processing.
"""

VALIDATION_FAILED = """
❌ Input Validation Failed

**Issues found:** {issues}

Please resolve these issues before proceeding.
"""

# Progress messages
PROGRESS_UPDATE = """
📊 Workflow Progress Update

**Current Progress:** {progress_percentage}% ({completed_nodes}/{total_nodes} nodes)
**Current Node:** {current_node}
**Status:** {status}

{additional_info}
"""

# Handoff messages
HANDOFF_TO_PARAMETER_HANDLER = """
🔧 Parameter Configuration Required

Handing off to Parameter Handler Agent for configuration file modification.
This is required for proper tool execution.

Please wait while parameters are configured...
"""

HANDOFF_TO_GENOTYPE_PHASING = """
🧬 Genotype Phasing Required

Handing off to Genotype Phasing Agent for genotype phasing.
This is required for omnibus test analysis.

Please wait while genotype phasing is completed...
"""

HANDOFF_RETURN_MESSAGE = """
🔄 Returning to Workflow

Parameter configuration/genotype phasing completed successfully.
Resuming workflow execution...
"""

# Template strings for formatting
EXECUTION_PLAN_TEMPLATE = """
{step_number}. {node_name}: {node_description}
   └── Expected outputs: {expected_outputs}
"""

OUTPUT_FILES_TEMPLATE = """
📁 Output Files from {node_name}
{file_list}
"""

WORKFLOW_SUMMARY_TEMPLATE = """
Workflow Summary:
- Start time: {start_time}
- End time: {end_time}
- Duration: {duration}
- Nodes executed: {nodes_executed}
- Files generated: {files_generated}
- Status: {status}
"""