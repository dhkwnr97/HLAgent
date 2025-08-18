#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
omnibus_utils.py
================
Utility functions and helper classes for OmnibusTest operations.

This module provides additional utility functions that may be needed
for OmnibusTest operations, independent of HATK.py.

Author: HLAgent Development Team
Date: 2025
"""

import os
import sys
from typing import Dict, List, Optional, Union
from pathlib import Path


class OmnibusTestUtils:
    """
    Utility class for OmnibusTest operations.
    """
    
    @staticmethod
    def validate_aa_file(aa_file_path: str) -> bool:
        """
        Validate that an .aa file has the correct format.
        
        Args:
            aa_file_path: Path to the .aa file
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not os.path.exists(aa_file_path):
            return False
            
        try:
            with open(aa_file_path, 'r') as f:
                # Read first few lines to check format
                lines = [f.readline().strip() for _ in range(5)]
                
            # Basic validation - should have header and data
            if len(lines) < 2:
                return False
                
            # Check if first line looks like a header
            header = lines[0].split()
            if len(header) < 3:  # Should have at least sample info
                return False
                
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def validate_bgl_phased_file(bgl_file_path: str) -> bool:
        """
        Validate that a .bgl.phased file has the correct format.
        
        Args:
            bgl_file_path: Path to the .bgl.phased file
            
        Returns:
            bool: True if valid, False otherwise
        """
        if not os.path.exists(bgl_file_path):
            return False
            
        try:
            with open(bgl_file_path, 'r') as f:
                first_line = f.readline().strip()
                
            # Check if it starts with marker information
            # Typical beagle format starts with marker info
            if not first_line or len(first_line.split()) < 3:
                return False
                
            return True
            
        except Exception:
            return False
    
    @staticmethod
    def parse_condition_string(condition_str: str) -> List[str]:
        """
        Parse a condition string into a list of individual conditions.
        
        Args:
            condition_str: Comma-separated condition string (e.g., "AA_DRB1_96,AA_DRB1_13")
            
        Returns:
            List[str]: List of individual conditions
        """
        if not condition_str or condition_str.lower() in ['none', 'null', '']:
            return []
            
        # Split by comma and clean up whitespace
        conditions = [cond.strip() for cond in condition_str.split(',')]
        
        # Filter out empty strings
        conditions = [cond for cond in conditions if cond]
        
        return conditions
    
    @staticmethod
    def get_output_filename(output_prefix: str, conditions: Optional[List[str]] = None) -> str:
        """
        Generate the output filename based on prefix and conditions.
        
        Args:
            output_prefix: Base output prefix
            conditions: List of conditions applied
            
        Returns:
            str: Complete output filename
        """
        if conditions and len(conditions) > 0:
            condition_str = ','.join(conditions)
            return f"{output_prefix}.{condition_str}.omnibus"
        else:
            return f"{output_prefix}.omnibus"
    
    @staticmethod
    def check_r_environment() -> bool:
        """
        Check if R and Rscript are available in the system.
        
        Returns:
            bool: True if R environment is available, False otherwise
        """
        try:
            import subprocess
            
            # Check for Rscript
            result = subprocess.run(['Rscript', '--version'], 
                                  capture_output=True, text=True)
            return result.returncode == 0
            
        except FileNotFoundError:
            return False
        except Exception:
            return False
    
    @staticmethod
    def create_backup_config(config_dict: Dict, backup_path: str) -> bool:
        """
        Create a backup of the configuration for reproducibility.
        
        Args:
            config_dict: Configuration dictionary
            backup_path: Path where to save the backup
            
        Returns:
            bool: True if backup was created successfully
        """
        try:
            import yaml
            from datetime import datetime
            
            # Add timestamp to config
            config_with_timestamp = config_dict.copy()
            config_with_timestamp['_backup_created'] = datetime.now().isoformat()
            
            with open(backup_path, 'w') as f:
                yaml.dump(config_with_timestamp, f, default_flow_style=False)
            
            return True
            
        except Exception:
            return False


def get_omnibus_test_version() -> str:
    """
    Get the version information for OmnibusTest module.
    
    Returns:
        str: Version string
    """
    return "OmnibusTest v1.0 - HLAgent Integration"


def print_omnibus_test_info():
    """
    Print information about the OmnibusTest module.
    """
    print("="*50)
    print("OMNIBUS TEST MODULE INFO")
    print("="*50)
    print(f"Version: {get_omnibus_test_version()}")
    print("Purpose: Likelihood ratio test for HLA amino acid positions")
    print("Dependencies: R environment with required packages")
    print("Input: Phased amino acid data (.aa) or phased beagle files (.bgl.phased)")
    print("Output: Statistical results with -log10(P-values)")
    print("="*50)


if __name__ == "__main__":
    print_omnibus_test_info()
