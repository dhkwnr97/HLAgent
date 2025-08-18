"""
Prompts for Genotype Phasing Agent.
"""

PHASING_PROMPTS = {
    "welcome_message": """
🧬 Welcome to the Genotype Phasing Agent! 🧬

I'm a professional genotype phasing agent that uses BEAGLE tool to perform high-quality genotype phasing.

SUPPORTED INPUT FORMATS:
• VCF files (.vcf)
• PLINK binary files (.bed, .bim, .fam)
• BEAGLE format files (.bgl, .markers)

Please prepare your genotype data in one of these formats before proceeding.
    """,
    
    "input_format_info": """
📋 SUPPORTED INPUT FORMATS:

1. VCF FORMAT:
   - Single file with .vcf extension
   - Contains genotype data in Variant Call Format

2. PLINK FORMAT:
   - Three files required: .bed, .bim, .fam
   - Binary format for efficient processing

3. BEAGLE FORMAT:
   - Two files required: .bgl, .markers
   - BEAGLE version 3 format

Please ensure your data is in one of these formats.
    """,
    
    "ready_prompt": """
Are you ready to proceed with genotype phasing?

Type:
• 'ready' - to proceed with phasing
• 'not ready' - to cancel and return to idle state  
• 'other types' - if you have data in other formats (will handoff to file converter)
    """,
    
    "file_conversion_needed": """
🔄 FILE CONVERSION NEEDED

You indicated that you have genotype data in other formats.
Please convert your data to PLINK format (.bed, .bim, .fam) first.

I'm now handing you off to the File Converter Agent to help with this conversion.
    """,
    
    "parameter_modification": """
🔧 PARAMETER CONFIGURATION

Now I'll handoff to the Parameter Handler Agent to configure the phasing parameters.
You can modify the YAML configuration file as needed.
    """,
    
    "phasing_execution": """
🧬 EXECUTING GENOTYPE PHASING

Starting BEAGLE phasing analysis...
This may take several minutes depending on your data size.
    """,
    
    "phasing_complete": """
✅ GENOTYPE PHASING COMPLETED!

Your genotype phasing has been completed successfully.
The following output files have been generated:
    """,
    
    "phasing_error": """
❌ GENOTYPE PHASING FAILED

An error occurred during the phasing process:
{error_message}

Please check your input data and try again.
    """,
    
    "cancel_message": """
❌ GENOTYPE PHASING CANCELLED

You chose 'not ready'. The phasing workflow has been cancelled.
Returning to idle state.
    """,
    
    "invalid_input": """
❓ INVALID INPUT

I don't understand your input: "{user_input}"

Please respond with:
• 'ready' - to proceed with phasing
• 'not ready' - to cancel
• 'other types' - if you need file conversion
    """,
    
    "system_prompt": """
You are a professional genotype phasing agent. Your role is to:
1. Guide users through the genotype phasing process
2. Validate input formats (VCF, PLINK, BEAGLE)
3. Coordinate with parameter handler for configuration
4. Execute BEAGLE phasing analysis
5. Return output file paths to users

Be professional, clear, and helpful in all communications.
    """
}