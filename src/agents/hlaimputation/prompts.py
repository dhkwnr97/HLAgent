"""
Prompts and message templates for HLA Imputation Agent.

Contains all user-facing messages, prompts, and templates used throughout the HLA imputation workflow.
"""

HLA_IMPUTATION_PROMPTS = {
    "welcome_message": """
🧬 === HLA IMPUTATION AGENT ===

Welcome to the advanced HLA imputation service! This agent helps you perform 
high-quality HLA typing and imputation using professional bioinformatics tools.
""",

    "tool_scanning": """
🔍 Scanning available HLA imputation tools...

Checking: /home/hanjg/App/Agents/HLAgent-main/src/tools/HLAimputation/
""",

    "available_tools_header": """
📋 Available HLA Imputation Tools:
==================================================
""",

    "tool_info_template": """
{number}. {display_name} ({name})
   📝 Description: {description}
   📂 Input Required: {input_description}
   ✨ Advantages: {advantages}
   ✅ Status: {status}
""",

    "tool_selection_prompt": """
==================================================

Please select an HLA imputation tool by entering:
• Tool name (e.g., "optitype", "cookhla", "hlahd")
• Tool number (e.g., "1", "2", "3")

Default tool: cookhla (if you just press Enter)

To HLA Imputation Agent: """,

    "invalid_tool_selection": """
❌ Invalid selection: '{selection}'
Please choose from the available tools listed above.
""",

    "tool_not_supported": """
❌ Tool '{tool}' is not currently supported.
Tools with '_Notsupported' in their folder name are under development.
Please select a different tool.
""",

    "tool_selected": """
✅ Selected: {display_name}

{description}
""",

    "cookhla_input_requirements": """
📋 CookHLA Input Requirements:

CookHLA requires the following input files:
• PLINK binary format files (.bed, .bim, .fam)
• Reference panel data

Please ensure you have:
1. Genotype data in PLINK format (.bed, .bim, .fam files)
2. Reference panel data properly configured
3. All files are accessible in the correct directories

Are you ready to proceed?
""",

    "hlahd_input_requirements": """
📋 HLA-HD Input Requirements:

HLA-HD requires paired-end FASTQ files:
• R1.fastq file (first read)
• R2.fastq file (second read)

Please ensure you have:
1. High-quality paired-end sequencing data
2. FASTQ files properly formatted
3. Files accessible in the input directory

Are you ready to proceed?
""",

    "optitype_input_requirements": """
📋 OptiType Input Requirements:

OptiType requires paired-end FASTQ files:
• R1.fastq file (first read)
• R2.fastq file (second read)

Please ensure you have:
1. DNA or RNA sequencing data (specify type)
2. FASTQ files properly formatted
3. Files accessible in the input directory

Are you ready to proceed?
""",

    "ready_options": """
Please respond with:
• "ready" - If your input files are prepared and accessible
• "not ready" - If you need to prepare your files first
• "other types" - If you have different format files that need conversion

To HLA Imputation Agent: """,

    "invalid_ready_response": """
❌ Please respond with one of the following:
• "ready"
• "not ready" 
• "other types"

To HLA Imputation Agent: """,

    "not_ready_message": """
📝 Please prepare your input files according to the requirements above.
Run the agent again when your files are ready.

Returning to IDLE state...
""",

    "file_conversion_handoff": """
🔄 Initiating file conversion process...

Your data needs to be converted to the required format.
Handing off to File Converter Agent via Supervisor...
""",

    "parameter_modification": """
⚙️  Parameter Configuration Phase

Now configuring tool-specific parameters...
Handing off to Parameter Handler Agent for YAML modification...
""",

    "execution_started": """
🚀 Executing HLA Imputation

Running {tool_name} with configured parameters...
This may take several minutes depending on data size and complexity.
""",

    "execution_complete": """
✅ HLA IMPUTATION COMPLETED SUCCESSFULLY!

Generated output files:
""",

    "no_output_files": """
⚠️  Imputation completed but no output files were generated.
This might indicate:
• Configuration issues
• Input data problems
• Tool execution errors

Please check the logs for more details.
""",

    "cancelled_message": """
❌ HLA imputation workflow cancelled.
""",

    "error_message": """
❌ ERROR: {error}

The HLA imputation workflow encountered an error.
Please check your input files and configuration.
""",

    "completion_summary": """
🎉 Task Summary:
• Tool Used: {tool_name}
• Output Files: {file_count}
• Status: Completed Successfully

Thank you for using the HLA Imputation Agent!
""",

    "file_list_template": """• {filename}""",

    "return_to_supervisor": """
🔄 Returning control to Supervisor Agent...
""",

    "standalone_completion": """
🏁 HLA Imputation Agent session completed.
Thank you for using our service!
"""
}

# System prompt for LLM interactions (if needed)
SYSTEM_PROMPT = """
You are a professional HLA imputation assistant. You help users understand HLA imputation 
processes, validate their input requirements, and guide them through the workflow.

Always be:
- Clear and informative
- Professional and helpful
- Specific about requirements
- Encouraging and supportive

Focus on:
- HLA biology and genetics
- Bioinformatics workflows
- Data format requirements
- Quality control considerations
"""