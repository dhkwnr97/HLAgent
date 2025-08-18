"""
Tool functions for Genotype Phasing Agent.
Contains tools for workchain execution, file handling, and external integrations.
"""

import os
from typing import List
from pydantic_ai import RunContext

from .dependencies import GenotypePhasingDependencies, GenotypePhasingSession
from .models import GenotypePhasingResult
from src.core.workchain_pa import execute_workchain_pa
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


async def execute_genotype_phasing_workflow(
    ctx: RunContext[GenotypePhasingDependencies]
) -> GenotypePhasingResult:
    """
    Execute genotype phasing workflow using workchain_pa.
    
    Args:
        ctx: Runtime context with dependencies
        
    Returns:
        GenotypePhasingResult with execution details
    """
    try:
        logger.info(f"Starting genotype phasing workflow for session: {ctx.deps.session_id}")
        
        # Get configuration paths
        session = GenotypePhasingSession(ctx.deps)
        orig_yaml_file = session.get_phasing_config_path()
        python_script_path = session.get_phasing_script_path()
        
        # Execute workchain with specific output file suffixes for phasing
        wc_result = await execute_workchain_pa(
            orig_yaml_file=orig_yaml_file,
            python_script_path=python_script_path,
            output_file_prefixes=[],
            output_file_suffixes=[".aa", ".phased", ".bgl", ".markers"]
        )
        
        if wc_result:
            # Add output files to session
            session.add_output_files(wc_result)
            
            logger.info(f"Genotype phasing completed successfully. Generated {len(wc_result)} files")
            
            return GenotypePhasingResult(
                success=True,
                output_files=wc_result,
                message=f"Genotype phasing completed successfully! Generated {len(wc_result)} files."
            )
        else:
            logger.error("Workchain execution returned no results")
            return GenotypePhasingResult(
                success=False,
                output_files=[],
                message="Genotype phasing failed - no output files generated",
                error="Workchain execution returned empty results"
            )
            
    except Exception as e:
        error_msg = f"Error in genotype phasing workflow: {str(e)}"
        logger.error(error_msg)
        
        return GenotypePhasingResult(
            success=False,
            output_files=[],
            message="Genotype phasing failed due to an error",
            error=error_msg
        )




def format_output_files_message(output_files: List[str]) -> str:
    """
    Format output files list for user display.
    
    Args:
        output_files: List of output file paths
        
    Returns:
        Formatted message string
    """
    if not output_files:
        return "No output files generated."
    
    file_list = []
    for file_path in output_files:
        filename = os.path.basename(file_path)
        file_list.append(f"   - {filename}")
    
    return "\n".join(file_list)


def validate_file_formats(user_input: str) -> bool:
    """
    Validate if user mentions supported file formats.
    
    Args:
        user_input: User's input string
        
    Returns:
        True if supported formats mentioned, False otherwise
    """
    user_input_lower = user_input.lower()
    supported_formats = [
        '.vcf', '.bgl', '.markers', '.bed', '.bim', '.fam',
        'vcf', 'beagle', 'plink', 'binary'
    ]
    
    return any(fmt in user_input_lower for fmt in supported_formats)