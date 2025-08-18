"""
Tools for File Converter Agent.

Provides conversion tools for genotype files and imputation tool outputs.
"""

import os
from dotenv import load_dotenv
import glob
import subprocess
import asyncio
import re
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
from langchain_core.tools import tool

from .agent_types import ImputationTool, GenotypeFunction, ConversionRequest
from src.core.workchain import create_workchain


load_dotenv()


class FileConverterTools:
    """Tools for file conversion operations."""
    
    def __init__(self, supervisor_handoff_callback: Optional[callable] = None):
        """Initialize the converter tools."""
        self.supervisor_handoff_callback = supervisor_handoff_callback
        self.workchain = create_workchain(supervisor_handoff_callback=supervisor_handoff_callback)
        self.output_directory = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"),"data/output/ConvertGT")
        self.filehandlers_directory = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"),"src/tools/filehandlers")
        
        # Java tool paths
        self.beagle2vcf_jar = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"),"src/tools/HATK/dependency/beagle2vcf.jar")
        self.vcf2beagle_jar = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"),"src/tools/HATK/dependency/vcf2beagle.jar")
    
    def scan_imputation_tools(self) -> List[ImputationTool]:
        """
        Scan filehandlers directory for available HLA imputation tools.
        
        Returns:
            List of ImputationTool objects with tool information
        """
        tools = []
        
        try:
            # Pattern: convert_hla_TOOLNAME2hped.py
            pattern = os.path.join(self.filehandlers_directory, "convert_hla_*2hped.py")
            tool_files = glob.glob(pattern)
            
            for tool_file in sorted(tool_files):
                # Extract tool name from filename
                filename = os.path.basename(tool_file)
                match = re.match(r'convert_hla_(.+?)2hped\.py', filename)
                
                if match:
                    tool_name = match.group(1)
                    
                    # Generate corresponding config path
                    config_file = f"convert_hla_{tool_name}2hped_run_config_orig.yaml"
                    config_path = os.path.join(self.filehandlers_directory, config_file)
                    
                    # Verify config file exists
                    if os.path.exists(config_path):
                        tool = ImputationTool(
                            name=tool_name,
                            display_name=tool_name.upper(),
                            script_path=tool_file,
                            config_path=config_path,
                            description=f"Convert {tool_name} imputation output to .hped format"
                        )
                        tools.append(tool)
        
        except Exception as e:
            print(f"Error scanning imputation tools: {e}")
        
        return tools
    
    def format_tool_list(self, tools: List[ImputationTool]) -> str:
        """
        Format list of HLA imputation tools for display.
        
        Args:
            tools: List of ImputationTool objects
            
        Returns:
            Formatted string for display
        """
        if not tools:
            return "No HLA imputation tools found."
        
        formatted_lines = []
        for i, tool in enumerate(tools, 1):
            formatted_lines.append(f"{i}. **{tool.display_name}** - {tool.description}")
        
        return "\n".join(formatted_lines)
    
    def find_tool_by_name_or_number(self, tools: List[ImputationTool], 
                                   selection: str) -> Optional[ImputationTool]:
        """
        Find imputation tool by name or number.
        
        Args:
            tools: List of available tools
            selection: User selection (name or number)
            
        Returns:
            Selected ImputationTool or None if not found
        """
        selection = selection.strip().lower()
        
        # Try to match by number
        try:
            tool_number = int(selection)
            if 1 <= tool_number <= len(tools):
                return tools[tool_number - 1]
        except ValueError:
            pass
        
        # Try to match by name
        for tool in tools:
            if tool.name.lower() == selection or tool.display_name.lower() == selection:
                return tool
        
        return None
    
    async def execute_genotype_function1(self) -> List[str]:
        """
        Execute genotype conversion Function 1: Various formats to PLINK binary.
        Uses workchain for parameter handling and execution.
        
        Returns:
            List of output file paths
        """
        try:
            yaml_path = os.path.join(self.filehandlers_directory, "convert_gt_run_config_orig.yaml")
            python_script = os.path.join(self.filehandlers_directory, "convert_gt.py")
            
            output_files = await self.workchain.execute_workchain(
                yaml_path=yaml_path,
                python_script_path=python_script,
                output_file_extensions=[".bed", ".bim", ".fam"],
                output_file_prefixes=[]
            )
            
            return output_files
            
        except Exception as e:
            print(f"Error executing Function 1: {e}")
            return []
    
    async def execute_genotype_function2(self, chrom: str, markers_file: str, 
                                       bgl_file: str, missing: str, 
                                       output_filename: str) -> List[str]:
        """
        Execute genotype conversion Function 2: Beagle v3 to VCF.
        
        Args:
            chrom: Chromosome identifier
            markers_file: Path to .markers file
            bgl_file: Path to .bgl file
            missing: Missing allele code
            output_filename: Output VCF filename
            
        Returns:
            List of output file paths
        """
        try:
            # Ensure output directory exists
            os.makedirs(self.output_directory, exist_ok=True)
            
            # Full output path
            output_path = os.path.join(self.output_directory, output_filename)
            
            # Build command
            cmd = [
                "java", "-jar", self.beagle2vcf_jar,
                chrom, markers_file, bgl_file, missing
            ]
            
            # Execute command and redirect output
            with open(output_path, 'w') as output_file:
                result = subprocess.run(
                    cmd,
                    stdout=output_file,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            
            if result.returncode == 0:
                return [output_path]
            else:
                error_msg = result.stderr or "Unknown error"
                print(f"beagle2vcf failed: {error_msg}")
                return []
                
        except subprocess.TimeoutExpired:
            print("beagle2vcf timed out")
            return []
        except Exception as e:
            print(f"Error executing Function 2: {e}")
            return []
    
    async def execute_genotype_function3(self, vcf_file: str, missing: str, 
                                       prefix: str) -> List[str]:
        """
        Execute genotype conversion Function 3: VCF to Beagle v3.
        
        Args:
            vcf_file: Path to input VCF file
            missing: Missing allele code for output
            prefix: Output file prefix
            
        Returns:
            List of output file paths
        """
        try:
            # Ensure output directory exists
            os.makedirs(self.output_directory, exist_ok=True)
            
            # Build command - vcf2beagle expects input via stdin
            cmd = [
                "java", "-jar", self.vcf2beagle_jar,
                missing, os.path.join(self.output_directory, prefix)
            ]
            
            # Execute command with VCF file as input
            with open(vcf_file, 'r') as input_file:
                result = subprocess.run(
                    cmd,
                    stdin=input_file,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=300  # 5 minute timeout
                )
            
            if result.returncode == 0:
                # vcf2beagle creates files with extensions: .markers, .bgl.gz, .int
                expected_files = [
                    os.path.join(self.output_directory, f"{prefix}.markers"),
                    os.path.join(self.output_directory, f"{prefix}.bgl.gz"),
                    os.path.join(self.output_directory, f"{prefix}.int")
                ]
                
                # Return only files that actually exist
                return [f for f in expected_files if os.path.exists(f)]
            else:
                error_msg = result.stderr or "Unknown error"
                print(f"vcf2beagle failed: {error_msg}")
                return []
                
        except subprocess.TimeoutExpired:
            print("vcf2beagle timed out")
            return []
        except Exception as e:
            print(f"Error executing Function 3: {e}")
            return []
    
    async def execute_imputation_conversion(self, tool: ImputationTool) -> List[str]:
        """
        Execute HLA imputation tool output conversion using workchain.
        
        Args:
            tool: Selected ImputationTool
            
        Returns:
            List of output file paths
        """
        try:
            output_files = await self.workchain.execute_workchain(
                yaml_path=tool.config_path,
                python_script_path=tool.script_path,
                output_file_extensions=[".hped"],
                output_file_prefixes=[]
            )
            
            return output_files
            
        except Exception as e:
            print(f"Error executing HLA imputation conversion for {tool.name}: {e}")
            return []
    
    def analyze_genotype_request(self, user_input: str) -> Optional[int]:
        """
        Analyze user's natural language request to determine genotype function.
        
        Args:
            user_input: User's natural language input
            
        Returns:
            Function number (1, 2, 3) or None if unclear
        """
        user_input = user_input.lower()
        
        # Function 1 indicators
        function1_inputs = ['.gen', '.sample', '.bgen', '.tped', '.tfam', '.ped', '.map', 
                           '.pgen', '.pvar', '.psam', '.vcf', '.vcf.gz', '.bcf']
        function1_outputs = ['.bed', '.bim', '.fam', 'plink', 'binary']
        
        # Function 2 indicators  
        function2_inputs = ['.bgl', '.markers', 'beagle']
        function2_outputs = ['.vcf', 'vcf']
        
        # Function 3 indicators
        function3_inputs = ['.vcf', 'vcf']
        function3_outputs = ['.bgl', '.markers', 'beagle']
        
        has_f1_input = any(inp in user_input for inp in function1_inputs)
        has_f1_output = any(out in user_input for out in function1_outputs)
        
        has_f2_input = any(inp in user_input for inp in function2_inputs)
        has_f2_output = any(out in user_input for out in function2_outputs)
        
        has_f3_input = '.vcf' in user_input
        has_f3_output = any(out in user_input for out in function3_outputs)
        
        # Determine function based on input/output combinations
        if has_f1_input and has_f1_output:
            return 1
        elif has_f2_input and has_f2_output:
            return 2
        elif has_f3_input and has_f3_output:
            return 3
        elif has_f1_output:  # Default to function 1 if wants PLINK output
            return 1
        
        return None
    
    def parse_function2_parameters(self, param_string: str) -> Optional[Tuple[str, str, str]]:
        """
        Parse Function 2 parameters from user input.
        
        Args:
            param_string: Comma-separated parameter string
            
        Returns:
            Tuple of (chrom, missing, output_filename) or None if invalid
        """
        try:
            parts = [p.strip() for p in param_string.split(',')]
            if len(parts) != 3:
                return None
                
            chrom, missing, output_filename = parts
            
            # Basic validation
            if not chrom or not missing or not output_filename:
                return None
                
            # Ensure output filename has .vcf extension
            if not output_filename.endswith('.vcf'):
                output_filename += '.vcf'
                
            return (chrom, missing, output_filename)
            
        except Exception:
            return None
    
    def parse_function3_parameters(self, param_string: str) -> Optional[Tuple[str, str]]:
        """
        Parse Function 3 parameters from user input.
        
        Args:
            param_string: Comma-separated parameter string
            
        Returns:
            Tuple of (missing, prefix) or None if invalid
        """
        try:
            parts = [p.strip() for p in param_string.split(',')]
            if len(parts) != 2:
                return None
                
            missing, prefix = parts
            
            # Basic validation
            if not missing or not prefix:
                return None
                
            return (missing, prefix)
            
        except Exception:
            return None
    
    def validate_input_files(self, file_paths: List[str]) -> bool:
        """
        Validate that input files exist.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            True if all files exist, False otherwise
        """
        for file_path in file_paths:
            if not os.path.exists(file_path):
                return False
        return True
    
    def format_output_files(self, output_files: List[str]) -> str:
        """
        Format output files list for display.
        
        Args:
            output_files: List of output file paths
            
        Returns:
            Formatted string for display
        """
        if not output_files:
            return "No output files generated."
        
        formatted_lines = []
        for file_path in output_files:
            formatted_lines.append(f"• {file_path}")
        
        return "\n".join(formatted_lines)


# Langchain tools for potential use in agent workflows
@tool
def scan_imputation_tools_tool() -> List[Dict[str, str]]:
    """
    Scan for available imputation conversion tools.
    
    Returns:
        List of dictionaries with tool information
    """
    tools_instance = FileConverterTools()
    tools = tools_instance.scan_imputation_tools()
    
    return [
        {
            "name": tool.name,
            "display_name": tool.display_name,
            "description": tool.description,
            "script_path": tool.script_path,
            "config_path": tool.config_path
        }
        for tool in tools
    ]


@tool
def analyze_genotype_request_tool(user_input: str) -> Optional[int]:
    """
    Analyze user's genotype conversion request.
    
    Args:
        user_input: User's natural language input
        
    Returns:
        Function number (1, 2, 3) or None if unclear
    """
    tools_instance = FileConverterTools()
    return tools_instance.analyze_genotype_request(user_input)


@tool
def validate_files_tool(file_paths: List[str]) -> bool:
    """
    Validate that files exist.
    
    Args:
        file_paths: List of file paths to validate
        
    Returns:
        True if all files exist
    """
    tools_instance = FileConverterTools()
    return tools_instance.validate_input_files(file_paths)