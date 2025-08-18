"""
Tools for New Genotype Phasing Agent.
"""

import os
import glob
from typing import List, Dict, Any
from pathlib import Path
from langchain_core.tools import tool

from .agent_types import InputFormat, InputValidationResult


class PhasingTools:
    """Tools for genotype phasing operations."""
    
    @staticmethod
    def detect_input_format(file_paths: List[str]) -> InputValidationResult:
        """
        Detect input format from file paths.
        
        Args:
            file_paths: List of file paths to analyze
            
        Returns:
            InputValidationResult with format detection results
        """
        if not file_paths:
            return InputValidationResult(
                is_valid=False,
                format_type=InputFormat.UNKNOWN,
                message="No files provided",
                files_found=[]
            )
        
        # Check for VCF format
        vcf_files = [f for f in file_paths if f.endswith('.vcf') or f.endswith('.vcf.gz')]
        if vcf_files:
            return InputValidationResult(
                is_valid=True,
                format_type=InputFormat.VCF,
                message=f"VCF format detected: {vcf_files[0]}",
                files_found=vcf_files
            )
        
        # Check for PLINK format
        bed_files = [f for f in file_paths if f.endswith('.bed')]
        bim_files = [f for f in file_paths if f.endswith('.bim')]
        fam_files = [f for f in file_paths if f.endswith('.fam')]
        
        if bed_files and bim_files and fam_files:
            return InputValidationResult(
                is_valid=True,
                format_type=InputFormat.PLINK,
                message=f"PLINK format detected: {bed_files[0]} (and .bim, .fam)",
                files_found=bed_files + bim_files + fam_files
            )
        
        # Check for BEAGLE format
        bgl_files = [f for f in file_paths if f.endswith('.bgl')]
        markers_files = [f for f in file_paths if f.endswith('.markers')]
        
        if bgl_files and markers_files:
            return InputValidationResult(
                is_valid=True,
                format_type=InputFormat.BEAGLE,
                message=f"BEAGLE format detected: {bgl_files[0]} (and .markers)",
                files_found=bgl_files + markers_files
            )
        
        return InputValidationResult(
            is_valid=False,
            format_type=InputFormat.UNKNOWN,
            message="No supported format detected. Please provide VCF, PLINK (.bed/.bim/.fam), or BEAGLE (.bgl/.markers) files.",
            files_found=file_paths
        )
    
    @staticmethod
    def validate_input_files(file_paths: List[str]) -> InputValidationResult:
        """
        Validate that input files exist and are readable.
        
        Args:
            file_paths: List of file paths to validate
            
        Returns:
            InputValidationResult with validation results
        """
        if not file_paths:
            return InputValidationResult(
                is_valid=False,
                format_type=InputFormat.UNKNOWN,
                message="No files provided for validation",
                files_found=[]
            )
        
        # Check if files exist
        existing_files = []
        missing_files = []
        
        for file_path in file_paths:
            if os.path.exists(file_path) and os.path.isfile(file_path):
                existing_files.append(file_path)
            else:
                missing_files.append(file_path)
        
        if missing_files:
            return InputValidationResult(
                is_valid=False,
                format_type=InputFormat.UNKNOWN,
                message=f"Missing files: {', '.join(missing_files)}",
                files_found=existing_files
            )
        
        # Detect format of existing files
        return PhasingTools.detect_input_format(existing_files)
    
    @staticmethod
    def find_files_in_directory(directory: str, patterns: List[str]) -> List[str]:
        """
        Find files matching patterns in a directory.
        
        Args:
            directory: Directory to search
            patterns: List of file patterns (e.g., ['*.vcf', '*.bed'])
            
        Returns:
            List of found file paths
        """
        found_files = []
        directory_path = Path(directory)
        
        if not directory_path.exists():
            return found_files
        
        for pattern in patterns:
            matches = glob.glob(str(directory_path / pattern))
            found_files.extend(matches)
        
        return sorted(found_files)
    
    @staticmethod
    def check_output_files(output_directory: str, 
                          expected_extensions: List[str]) -> List[str]:
        """
        Check for expected output files in the output directory.
        
        Args:
            output_directory: Directory to check
            expected_extensions: List of expected file extensions
            
        Returns:
            List of found output files
        """
        found_files = []
        
        for ext in expected_extensions:
            pattern = f"*{ext}"
            files = PhasingTools.find_files_in_directory(output_directory, [pattern])
            found_files.extend(files)
        
        return found_files


# Langchain tools for use in workflows
@tool
def detect_input_format_tool(file_paths: List[str]) -> Dict[str, Any]:
    """
    Detect input format from file paths.
    
    Args:
        file_paths: List of file paths to analyze
        
    Returns:
        Dictionary with format detection results
    """
    result = PhasingTools.detect_input_format(file_paths)
    return {
        "is_valid": result.is_valid,
        "format_type": result.format_type.value,
        "message": result.message,
        "files_found": result.files_found or []
    }


@tool
def validate_input_files_tool(file_paths: List[str]) -> Dict[str, Any]:
    """
    Validate that input files exist and are readable.
    
    Args:
        file_paths: List of file paths to validate
        
    Returns:
        Dictionary with validation results
    """
    result = PhasingTools.validate_input_files(file_paths)
    return {
        "is_valid": result.is_valid,
        "format_type": result.format_type.value,
        "message": result.message,
        "files_found": result.files_found or []
    }


@tool
def find_files_tool(directory: str, patterns: List[str]) -> List[str]:
    """
    Find files matching patterns in a directory.
    
    Args:
        directory: Directory to search
        patterns: List of file patterns
        
    Returns:
        List of found file paths
    """
    return PhasingTools.find_files_in_directory(directory, patterns)


@tool
def check_output_files_tool(output_directory: str, 
                           expected_extensions: List[str]) -> List[str]:
    """
    Check for expected output files.
    
    Args:
        output_directory: Directory to check
        expected_extensions: List of expected file extensions
        
    Returns:
        List of found output files
    """
    return PhasingTools.check_output_files(output_directory, expected_extensions)