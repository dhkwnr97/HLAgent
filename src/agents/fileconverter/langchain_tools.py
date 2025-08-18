"""
LangChain Tools for File Converter Agent.

Tools that can be used by the LangGraph create_react_agent.
"""

from typing import List
from langchain_core.tools import tool
from .tools import FileConverterTools


def get_all_conversion_tools(converter_tools: FileConverterTools) -> List:
    """
    Get all LangChain tools for the reactive agent.
    
    Args:
        converter_tools: FileConverterTools instance
        
    Returns:
        List of LangChain tools
    """
    return [
        scan_imputation_tools_tool,
        analyze_genotype_request_tool,
        validate_files_tool,
        execute_genotype_function1_tool,
        execute_genotype_function2_tool,
        execute_genotype_function3_tool,
        execute_imputation_conversion_tool
    ]


@tool
def scan_imputation_tools_tool() -> str:
    """Scan for available HLA imputation conversion tools."""
    from .tools import FileConverterTools
    tools_instance = FileConverterTools()
    tools = tools_instance.scan_imputation_tools()
    
    if not tools:
        return "No HLA imputation conversion tools found."
    
    return tools_instance.format_tool_list(tools)


@tool
def analyze_genotype_request_tool(user_request: str) -> str:
    """
    Analyze user's genotype conversion request to determine the best function.
    
    Args:
        user_request: User's natural language description of conversion needs
        
    Returns:
        Recommended function number and description
    """
    from .tools import FileConverterTools
    tools_instance = FileConverterTools()
    function_number = tools_instance.analyze_genotype_request(user_request)
    
    if function_number:
        from .prompts import FILECONVERTER_PROMPTS
        function_desc = FILECONVERTER_PROMPTS["function_descriptions"][str(function_number)]
        return f"Recommended Function {function_number}: {function_desc}"
    else:
        return "Could not determine the best function from your request. Please specify more details about input and output formats."


@tool
def validate_files_tool(file_paths: List[str]) -> str:
    """
    Validate that input files exist and are accessible.
    
    Args:
        file_paths: List of file paths to validate
        
    Returns:
        Validation result message
    """
    from .tools import FileConverterTools
    tools_instance = FileConverterTools()
    
    if tools_instance.validate_input_files(file_paths):
        return f"All {len(file_paths)} files are valid and accessible."
    else:
        return "Some files are missing or inaccessible. Please check the file paths."


@tool
def execute_genotype_function1_tool() -> str:
    """Execute genotype conversion Function 1: Various formats to PLINK binary."""
    return "Function 1 requires workchain execution with parameter handler. This tool initiates the workflow."


@tool
def execute_genotype_function2_tool(chrom: str, markers_file: str, bgl_file: str, 
                                  missing: str, output_filename: str) -> str:
    """
    Execute genotype conversion Function 2: Beagle v3 to VCF.
    
    Args:
        chrom: Chromosome identifier (e.g., "1", "2", "X")
        markers_file: Path to Beagle v3 markers file
        bgl_file: Path to Beagle v3 genotypes file
        missing: Missing allele code (e.g., "0", "-")
        output_filename: Output VCF filename
    """
    return f"Function 2 will convert Beagle files to VCF format with chromosome {chrom}, saving as {output_filename}"


@tool
def execute_genotype_function3_tool(vcf_file: str, missing: str, prefix: str) -> str:
    """
    Execute genotype conversion Function 3: VCF to Beagle v3.
    
    Args:
        vcf_file: Path to input VCF file
        missing: Missing allele code for output Beagle file
        prefix: Output file prefix
    """
    return f"Function 3 will convert {vcf_file} to Beagle v3 format with prefix {prefix}"


@tool
def execute_imputation_conversion_tool(tool_name: str) -> str:
    """
    Execute imputation tool output conversion.
    
    Args:
        tool_name: Name of the imputation tool (e.g., "AXIOM", "HIBAG")
    """
    return f"Imputation conversion for {tool_name} requires workchain execution with parameter handler."