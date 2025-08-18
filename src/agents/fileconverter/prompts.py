"""
Prompts for File Converter Agent.

Provides LLM prompts for genotype and HLA imputation file conversion workflows.
"""

FILECONVERTER_PROMPTS = {
    "welcome_message": """
🔄 Welcome to the Professional File Converter Agent! 🔄

I'm your specialized agent for professional genotype file conversion and HLA imputation bioinformatics tool output conversion.

🧬 AVAILABLE SERVICES:
1. **Genotype File Conversion** - Convert various genotype file formats to PLINK binary format (.bed, .bim, .fam)
2. **HLA Imputation Output Conversion** - Convert various imputation tool outputs to .hped format

I can handle a wide variety of formats and provide professional-grade conversion services.

Starting fresh with clean output file list initialization...
    """,
    
    "mode_selection": """
Please choose the type of conversion you need:

Type:
• 'genotype converting' - for genotype file format conversion
• 'HLA imputation converting' - for HLA imputation tool output conversion
• 'Done!' - to finish and exit
    """,
    
    # Genotype conversion prompts
    "genotype_welcome": """
🧬 GENOTYPE FILE CONVERSION SERVICE

I can convert various genotype file formats to PLINK binary format (.bed, .bim, .fam).

Please describe what you want to convert in natural language.
For example: "I have VCF files and I want to convert to bed, bim, fam file set"
    """,
    
    "genotype_analysis_system": """
You are a genotype file conversion expert. Analyze the user's natural language request to determine:

1. Input file extensions mentioned (e.g., [".vcf"], [".gen", ".sample"], etc.)
2. Output file extensions mentioned (e.g., [".bed", ".bim", ".fam"])
3. Which conversion function should be used

Available conversion functions:
- Function 1: Various formats (.gen/.sample, .bgen/.sample, .tped/.tfam, .ped/.map, .pgen/.pvar/.psam, .vcf, .vcf.gz, .bcf) to .bed/.bim/.fam
- Function 2: Beagle v3 (.bgl, .markers) to VCF v4.1
- Function 3: VCF v4.1 to Beagle v3 (.bgl, .markers)

Respond with only the function number (1, 2, or 3) that best matches the user's request.
If unclear, respond with "unclear".
    """,
    
    "function_confirmation": """
Based on your request, I recommend using **Function {function_number}**:

{function_description}

Is this what you want to do?
Type:
• 'yes' - to proceed with this function
• 'no' - to see detailed information about all available functions
    """,
    
    "genotype_function_details": """
📋 AVAILABLE GENOTYPE CONVERSION FUNCTIONS:

**1. Various Formats to PLINK Binary (.bed, .bim, .fam)**
   Input: .gen/.sample, .bgen/.sample, .tped/.tfam, .ped/.map, .pgen/.pvar/.psam, .vcf, .vcf.gz, .bcf
   Output: .bed, .bim, .fam files
   
**2. Beagle v3 to VCF v4.1**
   Input: .bgl, .markers files
   Output: VCF v4.1 format file
   
**3. VCF v4.1 to Beagle v3**
   Input: VCF v4.1 format file
   Output: .bgl, .markers files

Please type the number (1, 2, or 3) of the function you want to use:
    """,
    
    # Function-specific prompts
    "function1_workflow": """
🔧 FUNCTION 1: Various Formats to PLINK Binary

Starting workflow for converting various genotype formats to PLINK binary format (.bed, .bim, .fam).
I will now handoff to the Parameter Handler Agent to configure the conversion parameters.
    """,
    
    "function2_params": """
🔧 FUNCTION 2: Beagle v3 to VCF v4.1

Please provide the following parameters:

1. **Chromosome identifier** (e.g., "1", "2", "X"): 
2. **Missing allele code** in your Beagle genotypes file (e.g., "0", "-"): 
3. **Output VCF filename** (will be saved to /data/output/ConvertGT/): 

Please provide these parameters separated by commas.
Example: 1, 0, output.vcf
    """,
    
    "function3_params": """
🔧 FUNCTION 3: VCF v4.1 to Beagle v3

Please provide the following parameters:

1. **Missing allele code** for output Beagle file (e.g., "0", "-"): 
2. **Output file prefix** (will be saved to /data/output/ConvertGT/): 

Please provide these parameters separated by commas.
Example: 0, my_output_prefix
    """,
    
    # HLA imputation conversion prompts
    "imputation_welcome": """
🧬 HLA IMPUTATION OUTPUT CONVERSION SERVICE

I can convert various HLA imputation bioinformatics tool outputs to .hped format.

Let me scan available conversion tools for you...
    """,
    
    "imputation_tool_selection": """
📋 AVAILABLE HLA IMPUTATION TOOL CONVERTERS:

{tool_list}

Please select a tool by typing:
• The tool number (e.g., 1, 2, 3...)
• Or the tool name (e.g., "AXIOM", "HIBAG")
    """,
    
    "imputation_workflow": """
🔧 HLA IMPUTATION CONVERSION: {tool_name}

Starting workflow for converting {tool_name} imputation output to .hped format.
I will now handoff to the Parameter Handler Agent to configure the conversion parameters.
    """,
    
    # Completion and continuation prompts
    "conversion_complete": """
✅ CONVERSION COMPLETED!

Your file conversion has been completed successfully.
The following output files have been generated:

{output_files}

What would you like to do next?
Type:
• 'continue' - to perform another conversion
• 'Done!' - to finish and exit
    """,
    
    "workflow_error": """
❌ CONVERSION FAILED

An error occurred during the conversion process:
{error_message}

What would you like to do?
Type:
• 'continue' - to try another conversion
• 'Done!' - to finish and exit
    """,
    
    "invalid_input": """
❓ INVALID INPUT

I don't understand your input: "{user_input}"

Please provide a valid response.
    """,
    
    "goodbye_message": """
👋 FILE CONVERTER SESSION COMPLETED

Thank you for using the File Converter Agent!
All conversion tasks have been completed.
    """,
    
    # System prompts for LLM analysis
    "system_prompt": """
You are a professional file converter agent specializing in:
1. Genotype file format conversion
2. Imputation tool output conversion

Your role is to:
- Analyze user natural language requests intelligently
- Determine appropriate conversion functions automatically when possible
- Guide users through conversion workflows
- Coordinate with parameter handlers for configuration
- Execute conversion processes
- Provide clear status updates and file listings

Available genotype conversion functions:
- Function 1: Various formats (.bgen, .gen/.sample, .vcf, .ped/.map, .pgen/.pvar/.psam, .tped/.tfam, .bcf) to PLINK binary (.bed/.bim/.fam)
- Function 2: Beagle v3 (.bgl/.markers) to VCF v4.1
- Function 3: VCF v4.1 to Beagle v3 (.bgl/.markers)

When analyzing user requests, respond with exactly "function X" (where X is 1, 2, or 3) if you can clearly determine the best function.
Examples:
- "convert my .bgen file to plink format" → "function 1"
- "I need beagle to vcf conversion" → "function 2"  
- "convert vcf to beagle format" → "function 3"

Be professional, clear, and helpful in all communications.
    """,
    
    # Error handling prompts
    "parameter_error": """
❌ PARAMETER ERROR

There was an issue with the parameters you provided:
{error_details}

Please try again with the correct format.
    """,
    
    "file_not_found": """
❌ FILE ACCESS ERROR

Could not access the required files or directories:
{file_info}

Please check that your files are in the correct location and try again.
    """,
    
    "conversion_timeout": """
⏰ CONVERSION TIMEOUT

The conversion process is taking longer than expected.
This might be due to large file sizes or system load.

The process is still running in the background.
Type 'continue' to proceed with other tasks or 'Done!' to exit.
    """,
    
    # Function descriptions for confirmation prompts
    "function_descriptions": {
        "1": "Convert various genotype formats (.gen/.sample, .bgen/.sample, .tped/.tfam, .ped/.map, .pgen/.pvar/.psam, .vcf, .vcf.gz, .bcf) to PLINK binary format (.bed, .bim, .fam)",
        "2": "Convert Beagle v3 genotypes files (.bgl, .markers) to VCF version 4.1 format",
        "3": "Convert VCF version 4.1 format to Beagle v3 genotypes files (.bgl, .markers)"
    },
    
    # LLM analysis prompts for intelligent request processing
    "llm_analysis_prompt": """
User says: "{user_request}"

Please analyze this request and determine the best genotype conversion function:
- Function 1: Various formats (.bgen, .gen/.sample, .vcf, .ped/.map, etc.) to PLINK binary (.bed/.bim/.fam)
- Function 2: Beagle v3 (.bgl/.markers) to VCF v4.1 
- Function 3: VCF v4.1 to Beagle v3 (.bgl/.markers)

If the request clearly indicates one function, respond with just "function X" where X is 1, 2, or 3.
Examples:
- "I want convert my mybegen.bgen file to plink binary file" → "function 1"
- "convert my VCF to beagle format" → "function 3"
- "beagle to vcf conversion" → "function 2"
    """,
    
    # Java tool command templates
    "java_commands": {
        "beagle2vcf": "java -jar /home/hanjg/App/Agents/HLAgent-main/src/tools/HATK/dependency/beagle2vcf.jar {chrom} {markers} {bgl} {missing} > {output}",
        "vcf2beagle": "cat {vcf_file} | java -jar /home/hanjg/App/Agents/HLAgent-main/src/tools/HATK/dependency/vcf2beagle.jar {missing} {prefix}"
    }
}