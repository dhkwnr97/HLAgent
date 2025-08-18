"""
File Converter Agent
PydanticAI for parameter parsing.
"""
import os
from dotenv import load_dotenv
import asyncio
import subprocess
from pathlib import Path

# Fix for event loop issues with Gemini models
from src.utils.event_loop_fix import apply_event_loop_fix
apply_event_loop_fix()

from pydantic_ai import Agent
from pydantic import BaseModel, Field

from src.agents_pa.shared.universal_providers import get_fileconverter_model
from src.core.workchain_pa import execute_workchain_pa
from src.utils.logger import setup_logger


# Pydantic models for parameter parsing
class Beagle2VCFParameters(BaseModel):
    """Parameters for Beagle to VCF conversion"""
    chromosome: str = Field(..., description="Chromosome identifier for VCF file")
    markers_file: str = Field(..., description="Path to Beagle markers file")
    bgl_file: str = Field(..., description="Path to Beagle genotypes file")
    missing_code: str = Field(..., description="Missing allele code")
    output_vcf: str = Field(..., description="Output VCF file name")

class VCF2BeagleParameters(BaseModel):
    """Parameters for VCF to Beagle conversion"""
    vcf_file: str = Field(..., description="Path to input VCF file")
    missing_code: str = Field(..., description="Missing allele code")
    output_prefix: str = Field(..., description="Prefix for output Beagle files")


logger = setup_logger(__name__)


load_dotenv()


# Fresh agent creation functions to prevent event loop issues
def get_fresh_beagle_param_agent():
    """Create a fresh Beagle parameter agent to prevent event loop binding issues."""
    return Agent(
        get_fileconverter_model(),
        output_type=Beagle2VCFParameters,
        system_prompt=(
            "You are an assistant that parses natural language input into parameters for the beagle2vcf.jar command.\n"
            "The parameters are:\n"
            "- chromosome: the chromosome identifier (e.g., '6', '1', 'X')\n"
            "- markers_file: the path to the Beagle markers file (e.g., '/path/to/mymks.markers')\n"
            "- bgl_file: the path to the Beagle genotypes file (e.g., '/path/to/mybeagle.bgl')\n"
            "- missing_code: the missing allele code (e.g., '0' or '-')\n"
            "- output_vcf: the output VCF file name (e.g., 'myvcf_chr6.vcf')\n"
            "Given a natural language description, extract these parameters and return them in the required format.\n"
            "If any parameter is missing or unclear, use reasonable defaults or extract what you can."
        )
    )

def get_fresh_vcf_param_agent():
    """Create a fresh VCF parameter agent to prevent event loop binding issues."""
    return Agent(
        get_fileconverter_model(),
        output_type=VCF2BeagleParameters,
        system_prompt=(
            "You are an assistant that parses natural language input into parameters for the vcf2beagle.jar command.\n"
            "The parameters are:\n"
            "- vcf_file: the path to the input VCF file (e.g., 'myvcf.vcf')\n"
            "- missing_code: the missing allele code (e.g., '0' or '-')\n"
            "- output_prefix: the prefix for output Beagle files (e.g., 'mybeagle_convert')\n"
            "Given a natural language description, extract these parameters and return them in the required format.\n"
            "If any parameter is missing or unclear, use reasonable defaults or extract what you can."
        )
    )

# Fallback global agents for compatibility
beagle_param_agent = None
vcf_param_agent = None

# Simple state tracking
class SimpleState:
    def __init__(self):
        self.stage = "welcome"  # welcome, category, function, params, confirm
        self.category = None    # genotype, imputation
        self.function = None    # 1, 2, 3
        self.myoutputfile = []  # output files list
        self.parsed_params = None
        
    def reset(self):
        self.stage = "welcome"
        self.category = None
        self.function = None
        self.parsed_params = None
        # Don't reset myoutputfile here as it should persist across resets

# Global state for session
state = SimpleState()

# Simple chat function
async def simple_chat(user_input: str) -> str:
    global state
    user_input = user_input.strip()
    
    # Handle Done! at any stage first
    if user_input.lower() == "done!":
        state.reset()
        return "🎉 **File Converter session complete!** Goodbye!"
    
    # WELCOME STAGE
    if state.stage == "welcome":
        if user_input.lower() == "start":
            return """🔄 **File Converter Agent - Welcome!**

I can help you convert files in two categories:

**1. Genotype Converting** - Various genotype formats  
**2. Imputation Converting** - HLA imputation tool outputs to .hped format

Please type exactly:
- "genotype converting" for genotype file conversion
- "imputation converting" for HLA imputation output conversion

What would you like to convert?"""
    
    # CATEGORY SELECTION  
    if state.category is None:
        if user_input.lower() == "genotype converting":
            state.category = "genotype"
            state.stage = "function"
            return """🧬 **Genotype File Conversion - Category 1 Selected**

Please choose which genotype conversion function you need:

[1] Convert various formats to PLINK ver 1 binary (.bed, .bim, .fam)
    Supported inputs: .gen/.sample, .bgen/.sample, .tped/.tfam, .ped/.map, .pgen/.pvar/.psam, .vcf, .vcf.gz, .bcf

[2] Convert Beagle v3 (.bgl, .markers) to VCF ver 4.1 format (using beagle2vcf.jar)

[3] Convert VCF ver 4.1 to Beagle v3 format (using vcf2beagle.jar)

Please enter the number (1, 2, or 3) for your desired conversion function."""
            
        elif user_input.lower() == "imputation converting":
            state.category = "imputation"
            state.stage = "function"
            # Scan HLA tools and show menu immediately
            tools_dir = Path(os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/filehandlers"))
            hla_tools = []
            for script in tools_dir.glob("convert_hla_*2hped.py"):
                tool_name = script.stem.split('_')[2].replace('2hped', '').upper()
                hla_tools.append(tool_name)
            
            msg = ["🧬 **HLA Imputation Output Conversion**\n", "Available tools:"]
            for i, tool in enumerate(hla_tools, 1):
                msg.append(f"[{i}] {tool}")
            msg.append("\nPlease enter the number or tool name:")
            return '\n'.join(msg)
        elif user_input.lower() != "start":
            return """❌ **Invalid choice!**

Please type exactly:
- "genotype converting" for genotype file conversion  
- "imputation converting" for HLA imputation output conversion"""
    
    # FUNCTION SELECTION
    elif state.stage == "function":
        if state.category == "genotype":
            if user_input == "1":
                state.function = "1"
                return await execute_function_1()
            elif user_input == "2":
                state.function = "2"
                state.stage = "params"
                return """🔄 **Beagle v3 to VCF Conversion - Function 2**

I need these parameters for beagle2vcf.jar:
- [chrom]: Chromosome identifier (e.g., '1', '2', 'X')  
- [markers]: Beagle version 3 markers file
- [bgl]: Beagle version 3 genotypes file
- [missing]: Missing allele code (usually '0' or '-')
- [vcf]: Output VCF file name (Not Path)

**Example:**
"I want chromosome 6, markers file at /path/to/mymks.markers, bgl file at /path/to/mybeagle.bgl, missing allele code: 0 and I want output vcf named myvcf_chr6.vcf"

Please provide your parameters in natural language."""
            elif user_input == "3":
                state.function = "3" 
                state.stage = "params"
                return """🔄 **VCF to Beagle v3 Conversion - Function 3**

I need these parameters for vcf2beagle.jar:
- [vcf file]: Input VCF 4.1 format file
- [missing]: Missing allele code (usually '0' or '-')  
- [prefix]: Prefix for Beagle version 3 output files (Not Path)

**Example:**
"Lets convert vcf file myvcf.vcf, missing allele code: 0, and I want output prefix named mybeagle_convert"

Please provide your parameters in natural language."""
            else:
                return """❌ **Invalid choice!**

Please enter 1, 2, or 3:
[1] Convert to PLINK binary
[2] Convert Beagle to VCF  
[3] Convert VCF to Beagle"""
        
        elif state.category == "imputation":
            # Scan HLA tools dynamically (same logic as category selection)
            tools_dir = Path(os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/filehandlers"))
            hla_tools = []
            for script in tools_dir.glob("convert_hla_*2hped.py"):
                tool_name = script.stem.split('_')[2].replace('2hped', '').upper()
                hla_tools.append(tool_name)
            
            # Create dynamic tool mapping
            tool_map = {str(i): tool for i, tool in enumerate(hla_tools, 1)}
            
            # Handle tool selection
            choice = user_input.lower()
            if choice in tool_map or choice in [t.lower() for t in tool_map.values()]:
                if choice in tool_map:
                    tool = tool_map[choice]
                else:
                    tool = choice.upper()
                return await execute_imputation_output_conversion(tool)
            else:
                available_tools = ", ".join([f"{i}({tool})" for i, tool in tool_map.items()])
                return f"""❌ **Invalid HLA tool choice!**

Please enter a valid number or tool name from: {available_tools}"""
    
    # PARAMETER PARSING STAGE (PydanticAI parameter parsing)
    elif state.stage == "params":
        if state.function == "2":
            # PydanticAI parameter parsing for Beagle parameters
            try:
                # Create fresh agent to prevent event loop issues
                fresh_agent = get_fresh_beagle_param_agent()
                result = await fresh_agent.run(user_input)
                parsed = result.output
                
                params = {
                    'chromosome': str(parsed.chromosome).strip('"'),
                    'markers_file': str(parsed.markers_file).strip('"'),
                    'bgl_file': str(parsed.bgl_file).strip('"'),
                    'missing_code': str(parsed.missing_code).strip('"'),
                    'output_vcf': str(os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output/ConvertGT", parsed.output_vcf)).strip('"')
                }
                
                state.parsed_params = params
                state.stage = "confirm"
                return f"""🔍 **Parameter Parsing Complete**

Parsed parameters:
  chromosome: "{params['chromosome']}"\n\n
  markers_file: "{params['markers_file']}"\n\n
  bgl_file: "{params['bgl_file']}"\n\n
  missing_code: "{params['missing_code']}"\n\n
  output_vcf: "{params['output_vcf']}"

**Start Converting**

Type 'yes' to proceed or 'no' to re-enter parameters."""
            except Exception as e:
                # Handle event loop issues specifically
                if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                    logger.warning(f"Event loop issue detected in Beagle parameter parsing, creating fresh agent: {e}")
                    try:
                        # Reset any cached models and create fresh agent
                        from src.agents_pa.shared.universal_providers import universal_provider
                        universal_provider.clear_cache()
                        
                        fresh_agent = get_fresh_beagle_param_agent()
                        result = await fresh_agent.run(user_input)
                        parsed = result.output
                        
                        params = {
                            'chromosome': str(parsed.chromosome).strip('"'),
                            'markers_file': str(parsed.markers_file).strip('"'),
                            'bgl_file': str(parsed.bgl_file).strip('"'),
                            'missing_code': str(parsed.missing_code).strip('"'),
                            'output_vcf': str(os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output/ConvertGT", parsed.output_vcf)).strip('"')
                        }
                        
                        state.parsed_params = params
                        state.stage = "confirm"
                        logger.info("Successfully created fresh Beagle parameter agent after event loop fix")
                        return f"""🔍 **Parameter Parsing Complete**

Parsed parameters:
  chromosome: "{params['chromosome']}"\n\n
  markers_file: "{params['markers_file']}"\n\n
  bgl_file: "{params['bgl_file']}"\n\n
  missing_code: "{params['missing_code']}"\n\n
  output_vcf: "{params['output_vcf']}"

**Start Converting**

Type 'yes' to proceed or 'no' to re-enter parameters."""
                    except Exception as retry_e:
                        logger.error(f"Failed to create fresh agent after event loop fix: {retry_e}")
                        return f"❌ **Parameter parsing failed:** Event loop error occurred. Please try again with the correct format.\n\nError details: {str(e)}"
                else:
                    return f"❌ **Parameter parsing failed:** {str(e)}\n\nPlease try again with the correct format."
        
        elif state.function == "3":
            # PydanticAI parameter parsing for VCF parameters
            try:
                # Create fresh agent to prevent event loop issues
                fresh_agent = get_fresh_vcf_param_agent()
                result = await fresh_agent.run(user_input)
                parsed = result.output
                
                params = {
                    'vcf_file': str(parsed.vcf_file).strip('"'),
                    'missing_code': str(parsed.missing_code).strip('"'),
                    'output_prefix': str(os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output/ConvertGT", parsed.output_prefix)).strip('"')
                }
                
                state.parsed_params = params
                state.stage = "confirm"
                return f"""🔍 **Parameter Parsing Complete**

Parsed parameters:
  vcf_file: "{params['vcf_file']}"\n\n
  missing_code: "{params['missing_code']}"\n\n
  output_prefix: "{params['output_prefix']}"

**Start Converting**

Type 'yes' to proceed or 'no' to re-enter parameters."""
            except Exception as e:
                # Handle event loop issues specifically
                if "event loop" in str(e).lower() or "bound to a different" in str(e).lower():
                    logger.warning(f"Event loop issue detected in VCF parameter parsing, creating fresh agent: {e}")
                    try:
                        # Reset any cached models and create fresh agent
                        from src.agents_pa.shared.universal_providers import universal_provider
                        universal_provider.clear_cache()
                        
                        fresh_agent = get_fresh_vcf_param_agent()
                        result = await fresh_agent.run(user_input)
                        parsed = result.output
                        
                        params = {
                            'vcf_file': str(parsed.vcf_file).strip('"'),
                            'missing_code': str(parsed.missing_code).strip('"'),
                            'output_prefix': str(os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output/ConvertGT", parsed.output_prefix)).strip('"')
                        }
                        
                        state.parsed_params = params
                        state.stage = "confirm"
                        logger.info("Successfully created fresh VCF parameter agent after event loop fix")
                        return f"""🔍 **Parameter Parsing Complete**

Parsed parameters:
  vcf_file: "{params['vcf_file']}"\n\n
  missing_code: "{params['missing_code']}"\n\n
  output_prefix: "{params['output_prefix']}"

**Start Converting**

Type 'yes' to proceed or 'no' to re-enter parameters."""
                    except Exception as retry_e:
                        logger.error(f"Failed to create fresh VCF agent after event loop fix: {retry_e}")
                        return f"❌ **Parameter parsing failed:** Event loop error occurred. Please try again with the correct format.\n\nError details: {str(e)}"
                else:
                    return f"❌ **Parameter parsing failed:** {str(e)}\n\nPlease try again with the correct format."
    
    # CONFIRMATION STAGE
    elif state.stage == "confirm":
        if user_input.lower() == "yes":
            if state.function == "2":
                return execute_beagle_to_vcf()
            elif state.function == "3":
                return execute_vcf_to_beagle()
        elif user_input.lower() == "no":
            state.stage = "params"
            # Clear parsed params so user can re-enter them
            state.parsed_params = None
            
            # Return the appropriate parameter input prompt based on the function
            if state.function == "2":
                return """🔄 **Re-entering Parameters - Beagle v3 to VCF Conversion**

I need these parameters for beagle2vcf.jar:
- [chrom]: Chromosome identifier (e.g., '1', '2', 'X')  
- [markers]: Beagle version 3 markers file
- [bgl]: Beagle version 3 genotypes file
- [missing]: Missing allele code (usually '0' or '-')
- [vcf]: Output VCF file name (Not Path)

**Example:**
"I want chromosome 6, markers file at /path/to/mymks.markers, bgl file at /path/to/mybeagle.bgl, missing allele code: 0 and I want output vcf named myvcf_chr6.vcf"

Please provide your parameters in natural language."""
            elif state.function == "3":
                return """🔄 **Re-entering Parameters - VCF to Beagle v3 Conversion**

I need these parameters for vcf2beagle.jar:
- [vcf file]: Input VCF 4.1 format file
- [missing]: Missing allele code (usually '0' or '-')  
- [prefix]: Prefix for Beagle version 3 output files (Not Path)

**Example:**
"Lets convert vcf file myvcf.vcf, missing allele code: 0, and I want output prefix named mybeagle_convert"

Please provide your parameters in natural language."""
            else:
                return """❌ **Please try again with the correct format.**

Use the example format provided above to specify your parameters."""
        else:
            return "Please type 'yes' to proceed or 'no' to re-enter parameters."
    
    # FINAL STAGE - DONE/CONTINUE
    elif state.stage == "done":
        if user_input.lower() == "done!":
            state.reset()
            return "🎉 **File Converter session complete!** Goodbye!"
        elif user_input.lower() == "continue":
            state.reset()
            state.stage = "welcome"
            return await simple_chat("start")  # Show welcome again
        else:
            return """Please choose:


- Type 'Done!' to finish
- Type 'continue' for more conversions"""
    
    return "I don't understand. Please follow the instructions above."

# Helper functions for executing conversions
async def execute_function_1():
    """Execute genotype conversion function 1 using workchain_pa"""
    try:
        wc_result = await execute_workchain_pa(
            orig_yaml_file = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/filehandlers/convert_gt_run_config_orig.yaml"),
            python_script_path = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/filehandlers/convert_gt.py"),
            output_file_prefixes=[], 
            output_file_suffixes=[".bed", ".bim", ".fam"]
        )
        output_files = wc_result
        state.myoutputfile.extend(output_files)
        state.stage = "done"
        
        result = f"""✅ **Conversion Completed Successfully!**

Generated files:{state.myoutputfile}\n\n
Files stored in: data/output/ConvertGT

**What's next?**
- Type 'Done!' if finished
- Type 'continue' for more conversions"""
        
        return result
    except Exception as e:
        return f"❌ Error: {str(e)}"

def execute_beagle_to_vcf():
    """Execute Beagle to VCF conversion using beagle2vcf.jar"""
    try:
        # Parse parameters from state.parsed_params
        params = state.parsed_params
        if not params:
            return "❌ Error: No parameters found"
        
        # Paths
        jar_path = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/HATK/dependency/beagle2vcf.jar")
        output_dir = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output/ConvertGT")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Build output file path
        output_vcf = os.path.join(output_dir, params['output_vcf'])
        
        # Build Java command: java -jar beagle2vcf.jar [chrom] [markers] [bgl] [missing] > [vcf]
        cmd = [
            "java", "-jar", jar_path,
            params['chromosome'],
            params['markers_file'],
            params['bgl_file'],
            params['missing_code']
        ]
        
        logger.info(f"Executing Beagle to VCF conversion: {' '.join(cmd)} > {output_vcf}")
        
        # Execute command with output redirection
        with open(output_vcf, 'w') as output_file:
            result = subprocess.run(cmd, stdout=output_file, stderr=subprocess.PIPE, text=True, check=True)
        
        # Add to output files list
        state.myoutputfile.append(output_vcf)
        state.stage = "done"
        
        return f"""✅ **Beagle to VCF conversion completed!**

Generated file:
   - {params['output_vcf']}

Files stored in: {output_dir}

**What's next?**
- Type 'Done!' if finished
- Type 'continue' for more conversions"""
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode() if e.stderr else str(e))
        logger.error(f"Java execution failed: {error_msg}")
        return f"❌ **Java execution failed:** {error_msg}"
    except Exception as e:
        logger.error(f"Beagle to VCF conversion error: {str(e)}")
        return f"❌ **Error:** {str(e)}"

def execute_vcf_to_beagle():
    """Execute VCF to Beagle conversion using vcf2beagle.jar"""
    try:
        # Parse parameters from state.parsed_params
        params = state.parsed_params
        if not params:
            return "❌ Error: No parameters found"
        
        # Paths
        jar_path = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src/tools/HATK/dependency/vcf2beagle.jar")
        output_dir = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output/ConvertGT")
        
        # Ensure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        # Expected output files (Beagle creates .markers and .bgl files)
        output_markers = os.path.join(output_dir, f"{params['output_prefix']}.markers")
        output_bgl = os.path.join(output_dir, f"{params['output_prefix']}.bgl")
        
        # Build Java command: cat [vcf file] | java -jar vcf2beagle.jar [missing] [prefix]
        # We need to handle the pipe operation
        cat_cmd = ["cat", params['vcf_file']]
        java_cmd = ["java", "-jar", jar_path, params['missing_code'], os.path.join(output_dir, params['output_prefix'])]
        
        logger.info(f"Executing VCF to Beagle conversion: {' '.join(cat_cmd)} | {' '.join(java_cmd)}")
        
        # Execute with pipe: cat vcf_file | java -jar vcf2beagle.jar missing prefix
        cat_process = subprocess.Popen(cat_cmd, stdout=subprocess.PIPE)
        java_result = subprocess.run(java_cmd, stdin=cat_process.stdout, stderr=subprocess.PIPE, text=True, check=True)
        cat_process.stdout.close()
        cat_process.wait()
        
        # Add to output files list (check which files actually exist)
        generated_files = []
        if os.path.exists(output_markers):
            state.myoutputfile.append(output_markers)
            generated_files.append(f"{params['output_prefix']}.markers")
        if os.path.exists(output_bgl):
            state.myoutputfile.append(output_bgl)
            generated_files.append(f"{params['output_prefix']}.bgl")
        # Also check for .bgl.gz variant
        output_bgl_gz = f"{output_bgl}.gz"
        if os.path.exists(output_bgl_gz):
            state.myoutputfile.append(output_bgl_gz)
            generated_files.append(f"{params['output_prefix']}.bgl.gz")
        
        state.stage = "done"
        
        file_list = "\n".join([f"   - {f}" for f in generated_files])
        
        return f"""✅ **VCF to Beagle conversion completed!**

Generated files:
{file_list}

Files stored in: {output_dir}

**What's next?**
- Type 'Done!' if finished
- Type 'continue' for more conversions"""
        
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr if isinstance(e.stderr, str) else (e.stderr.decode() if e.stderr else str(e))
        logger.error(f"Java execution failed: {error_msg}")
        return f"❌ **Java execution failed:** {error_msg}"
    except Exception as e:
        logger.error(f"VCF to Beagle conversion error: {str(e)}")
        return f"❌ **Error:** {str(e)}"

async def execute_imputation_output_conversion(tool):
    """Execute HLA conversion using workchain_pa"""
    try:
        wc_result = await execute_workchain_pa(
            orig_yaml_file = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), f"src/tools/filehandlers/convert_hla_{tool}2hped_run_config_orig.yaml"),
            python_script_path = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), f"src/tools/filehandlers/convert_hla_{tool}2hped.py"),
            output_file_prefixes=[], 
            output_file_suffixes=[".hped"]
        )
        output_file = wc_result
        state.myoutputfile.extend(output_file)
        state.stage = "done"
        
        return f"""✅ **{tool} to HPED conversion completed!**

Generated files: {state.myoutputfile}
Files stored in: data/output/ConvertHPED

**What's next?**
- Type 'Done!' if finished
- Type 'continue' for more conversions"""
    except Exception as e:
        return f"❌ Error: {str(e)}"

# Handover compatibility wrapper
class FileConverterAgentPA:
    def __init__(self):
        pass
    
    async def initialize(self, deps):
        logger.info(f"Initializing File Converter agent for session: {getattr(deps, 'session_id', 'unknown')}")
        
        # Check if this is a fresh handover (after Done! command)
        session_id = getattr(deps, 'session_id', None)
        
        # Always reset for fresh handovers or if stage is invalid
        if (state.stage == "welcome" and state.category is None) or session_id is None:
            logger.info("Fresh session or clean state - keeping current state")
        else:
            logger.info(f"Resetting state from previous session - was at stage: {state.stage}, category:{state.category}")    
            state.reset()
        
        logger.info("File Converter agent initialized successfully")
    
    async def run(self, user_input, deps):
        logger.info(f"File converter processing query: '{user_input}' (current myoutputfile: {len(state.myoutputfile)} files)")
        
        if user_input == "Please show the welcome message and available conversion options":
            user_input = "start"
        
        return await simple_chat(user_input)
    
    async def chat_loop(self, deps, standalone=True):
        if standalone:
            print("File Converter interactive mode - type 'Done!' to exit")
        
        conversation_count = 0
        status = "active"
        
        try:
            print(await simple_chat("start"))
            while True:
                user_input = input(">>To file converter agent>> ").strip()
                conversation_count += 1
                
                if user_input.lower() == "done!":
                    status = "completed"
                    break
                    
                response = await simple_chat(user_input)
                print(f"File Converter: {response}")
                
        except KeyboardInterrupt:
            status = "interrupted"
        except Exception as e:
            status = f"error: {str(e)}"
        
        return {
            "conversation_count": conversation_count,
            "status": status,
            "conversions_completed": len(state.myoutputfile),
            "output_files": state.myoutputfile.copy()
        }

# Exports
fileconverter_agent_pa = FileConverterAgentPA()

# Simple functions for direct use
async def run_fileconverter_workflow(user_input: str, deps=None):
    return await fileconverter_agent_pa.run(user_input, deps or type('obj', (object,), {})())

async def run_fileconverter_sync(user_input: str, deps=None):
    return await run_fileconverter_workflow(user_input, deps)