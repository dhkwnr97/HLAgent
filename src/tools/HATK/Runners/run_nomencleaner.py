#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_nomencleaner.py
==================
NomenCleaner execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the NomenCleaner
function with the specified parameters.

Usage:
    python src/tools/HATK/NomenCleaner/run_nomencleaner.py [config_file]
    
    If no config file is specified, it will look for 'nomencleaner_run_config.yaml'
    in the NomenCleaner directory.

Author: HLAgent Development Team
Date: 2025
"""

import os
import sys
import time
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Union

# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

from src.tools.HATK.NomenCleaner import NomenCleaner
from src.tools.HATK.NomenCleaner.src.HPED import HPED
from src.tools.HATK.NomenCleaner.src.CHPED import CHPED


class NomenCleanerRunner:
    """
    NomenCleaner execution wrapper with YAML configuration support.
    """
    
    def __init__(self, config_f: str = None):
        # Get the directory containing this script
        current_dir = Path(__file__).parent
        
        # Set default config file if not provided
        if config_f is None:
            config_f = "nomencleaner_run_config.yaml"
        
        # If config_f is not an absolute path, make it relative to the script directory
        if not os.path.isabs(config_f):
            self.config_path = os.path.join(current_dir, config_f)
        else:
            self.config_path = config_f
            
        self.config = {}
        self.start_time = None
        self.end_time = None
        self._auto_output_prefix = True
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            print(f"✓ Configuration loaded from: {self.config_path}")
            return self.config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")
    
    def validate_config(self) -> bool:
        """Validate the configuration parameters."""
        required_params = ['_hped', '_hat']
        
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Required parameter '{param}' not found in configuration")
        
        # Convert relative paths to absolute paths based on current working directory
        for param in ['_hped', '_hat']:
            if not os.path.isabs(self.config[param]):
                self.config[param] = os.path.join(os.getcwd(), self.config[param])
        
        # Handle output prefix - can be null for auto-generation
        if self.config.get('_out_prefix'):
            if not os.path.isabs(self.config['_out_prefix']):
                self.config['_out_prefix'] = os.path.join(os.getcwd(), self.config['_out_prefix'])
        
        # Validate input files if enabled
        if self.config.get('_validation', {}).get('check_input_files', True):
            hped_path = self.config['_hped']
            hat_path = self.config['_hat']
            
            if not os.path.exists(hped_path):
                raise FileNotFoundError(f"HPED file not found: {hped_path}")
            if not os.path.exists(hat_path):
                raise FileNotFoundError(f"HAT file not found: {hat_path}")
            
            print(f"✓ Input files validated")
            print(f"  - HPED: {hped_path}")
            print(f"  - HAT: {hat_path}")
        
        
        try:
            hped_obj = HPED(self.config['_hped'])
            # Convert numpy strings to regular Python strings for clean display
            hped_hla_genes = set(str(gene) for gene in hped_obj.HLA_avail)
            
            # Get HLA target genes from config (user can specify any subset or superset)
            if '_HLA_target' in self.config and self.config['_HLA_target']:
                config_hla_genes = set(self.config['_HLA_target'])
            else:
                # Default 8 major HLA genes if not specified in config
                config_hla_genes = set(["A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1"])
            
            missing_genes = config_hla_genes - hped_hla_genes
            if missing_genes:
                raise ValueError(f"❌ Index out of range! HPED file missing HLA genes: {missing_genes}\n"
                               f"   HPED contains: {sorted(hped_hla_genes)}\n"
                               f"   Config requests: {sorted(config_hla_genes)}")
            
            print(f"✓ HLA gene compatibility verified")
            print(f"  - HPED genes: {sorted(hped_hla_genes)}")
            print(f"  - Config genes: {sorted(config_hla_genes)}")
        except ImportError:
            print("⚠️  Could not verify HLA gene compatibility (HPED module not found)")
        except Exception as e:
            print(f"⚠️  Could not verify HLA gene compatibility: {e}")
        
        return True
    
    def parse_output_format(self, format_input: Union[str, List[str]]) -> List[int]:
        """Convert string/list output format to numeric format list."""
        format_mapping = {
            "1field": 1, "2field": 2, "3field": 3, "4field": 4,
            "ggroup": 5, "pgroup": 6, "default": 0
        }
        
        # [요구사항3] 여러 format 지원
        if isinstance(format_input, list):
            return [self._parse_single_format(f, format_mapping) for f in format_input]
        else:
            return [self._parse_single_format(format_input, format_mapping)]
    
    def _parse_single_format(self, format_str, format_mapping):
        """Parse single format string."""
        if isinstance(format_str, int):
            return format_str
        if format_str.lower() in format_mapping:
            return format_mapping[format_str.lower()]
        try:
            return int(format_str)
        except ValueError:
            raise ValueError(f"Invalid output format: {format_str}")
    
    def _get_format_name(self, format_num):
        """Get format name from number."""
        format_names = {0: 'default', 1: '1field', 2: '2field', 3: '3field', 
                       4: '4field', 5: 'ggroup', 6: 'pgroup'}
        return format_names.get(format_num, f'format{format_num}')
    
    def _extract_imgt_version(self, hat_path: str) -> str:
        """Extract IMGT version from HAT file path."""
        import re
        
        # Extract filename from path
        hat_filename = os.path.basename(hat_path)
        
        # Look for pattern like "imgt3600", "imgt370", etc.
        match = re.search(r'imgt(\d+)', hat_filename, re.IGNORECASE)
        if match:
            return f"imgt{match.group(1)}"
        
        # If no IMGT version found in filename, return default
        print(f"Warning: Could not extract IMGT version from HAT file '{hat_filename}'. Using default 'imgt3600'.")
        return "imgt3600"
    
    def create_output_directory(self, out_prefix: str):
        """Create output directory if it doesn't exist."""
        if self.config.get('_create_output_dir', True):
            out_dir = os.path.dirname(out_prefix)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
                print(f"✓ Created output directory: {out_dir}")
    
    def print_configuration_summary(self):
        """Print a summary of the configuration."""
        print("\n" + "="*60)
        print("NOMENCLEANER CONFIGURATION SUMMARY")
        print("="*60)
        print(f"Input HPED file:     {self.config['_hped']}")
        print(f"Input HAT file:      {self.config['_hat']}")
        
        # Extract and show IMGT version from HAT file
        imgt_version = self._extract_imgt_version(self.config['_hat'])
        print(f"IMGT version:        {imgt_version} (extracted from HAT file)")
        
        print(f"Output prefix:       {self.config.get('_out_prefix', 'auto-generated')}")
        print(f"Output format:       {self.config.get('_output_format', 'default')}")
        print(f"No gene prefix:      {self.config.get('_f_NoGenePrefix', False)}")
        print(f"Leave not found:     {self.config.get('_f_leave_NotFound', False)}")
        
        # Get HLA target genes for display
        if '_HLA_target' in self.config and self.config['_HLA_target']:
            hla_targets = self.config['_HLA_target']
        elif '_HLA_target_extended' in self.config and self.config['_HLA_target_extended']:
            hla_targets = self.config['_HLA_target_extended']
        else:
            hla_targets = ["A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1"]
        print(f"HLA targets:         {', '.join(hla_targets)}")
        print("="*60)
    
    def run_nomencleaner(self) -> List[Tuple[str, str, str]]:
        """Execute the NomenCleaner function."""
        hped_path = self.config['_hped']
        hat_path = self.config['_hat']
        base_out_prefix = self.config.get('_out_prefix')
        
        # Get the base filename from HPED input
        hped_basename = os.path.splitext(os.path.basename(hped_path))[0]
        
        # Extract IMGT version from HAT file path
        imgt_version = self._extract_imgt_version(hat_path)
        
        # Prepare other parameters
        f_no_gene_prefix = self.config.get('_f_NoGenePrefix', False)
        f_leave_not_found = self.config.get('_f_leave_NotFound', False)
        
        # Get HLA target genes from config (user can specify any subset or superset)
        if '_HLA_target' in self.config and self.config['_HLA_target']:
            hla_target = tuple(self.config['_HLA_target'])
        elif '_HLA_target_extended' in self.config and self.config['_HLA_target_extended']:
            hla_target = tuple(self.config['_HLA_target_extended'])
        else:
            # Default 8 major HLA genes
            hla_target = tuple(["A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1"])
        
        # Show progress if enabled
        if self.config.get('_performance', {}).get('show_progress', True):
            print("\n🔄 Starting NomenCleaner processing...")
            print(f"📋 Extracted IMGT version: {imgt_version}")
        
        # Measure execution time if enabled
        if self.config.get('_performance', {}).get('measure_time', True):
            self.start_time = time.time()
        
        output_formats = self.parse_output_format(self.config.get('_output_format', 'default'))
        results = []
        
        # Create output directory, allowing override from config file
        output_dir = self.config.get('_output_dir', "data/output/NomenCleaner")
        if self.config.get('_create_output_dir', True):
            os.makedirs(output_dir, exist_ok=True)
            print(f"✓ Created output directory: {output_dir}")
        
        for i, output_format in enumerate(output_formats):
            format_name = self._get_format_name(output_format)
            # Each format gets its own prefix: basename_imgtversion_formatname
            current_out_prefix = f"{output_dir}/{hped_basename}_{imgt_version}_{format_name}"
            
            print(f"\n🔄 Processing format {i+1}/{len(output_formats)}: {format_name}")
            
            try:
                chped_file, log_file = NomenCleaner.NomenCleaner(
                    _hped=hped_path,
                    _hat=hat_path,
                    _out_prefix=current_out_prefix,
                    _OUTPUT_FORMAT=output_format,
                    _f_NoGenePrefix=f_no_gene_prefix,
                    _f_leave_NotFound=f_leave_not_found,
                    _HLA_target=hla_target
                )
                results.append((chped_file, log_file, format_name))
                print(f"✅ Completed format {format_name}")
            except Exception as e:
                raise RuntimeError(f"NomenCleaner execution failed for {format_name}: {e}")
        
        if self.config.get('_performance', {}).get('measure_time', True):
            self.end_time = time.time()
        
        # Store the summary prefix for save_summary method
        format_names = [self._get_format_name(fmt) for fmt in output_formats]
        summary_suffix = '_'.join(format_names)
        self.summary_prefix = f"{output_dir}/{hped_basename}_{imgt_version}_{summary_suffix}"
        
        return results
    
    def print_results_summary(self, results: List[Tuple[str, str, str]]):
        """Print a summary of the results."""
        print("\n" + "="*60)
        print("NOMENCLEANER RESULTS SUMMARY")
        print("="*60)
        
        for i, (chped_file, log_file, format_name) in enumerate(results):
            print(f"\n📋 Results for format: {format_name}")
            print("-" * 40)
            
            # Check output files
            if os.path.exists(chped_file):
                chped_size = os.path.getsize(chped_file)
                print(f"✓ CHPED file created: {chped_file} ({chped_size:,} bytes)")
            else:
                print(f"✗ CHPED file not found: {chped_file}")
                
            if os.path.exists(log_file):
                log_size = os.path.getsize(log_file)
                print(f"✓ Log file created:   {log_file} ({log_size:,} bytes)")
            else:
                print(f"✗ Log file not found: {log_file}")
            
            # Analyze CHPED file if it exists
            if os.path.exists(chped_file):
                try:
                    chped = CHPED(chped_file)
                    print(f"📊 HLA genes processed: {', '.join(chped.HLA_avail)}")
                    print(f"📊 Field format:       {chped.field_format}")
                    print(f"📊 All CHPED alleles:  {chped.isAllCHPEDallele}")
                except Exception as e:
                    print(f"⚠️  Could not analyze CHPED file: {e}")
        
        # Show execution time
        if self.start_time and self.end_time:
            execution_time = self.end_time - self.start_time
            print(f"\n⏱️  Total execution time: {execution_time:.2f} seconds")
        
        print("="*60)
    
    def save_summary(self, results: List[Tuple[str, str, str]]):
        """Save processing summary to file."""
        if self.config.get('_save_summary', True):
            # Use the summary prefix set in run_nomencleaner
            summary_file = getattr(self, 'summary_prefix', 'nomencleaner_output') + '.summary.txt'
            
            with open(summary_file, 'w') as f:
                f.write("NomenCleaner Processing Summary\n")
                f.write("="*40 + "\n\n")
                f.write(f"Configuration file: {self.config_path}\n")
                f.write(f"Input HPED: {self.config['_hped']}\n")
                f.write(f"Input HAT: {self.config['_hat']}\n")
                f.write(f"Output format(s): {self.config.get('_output_format', 'default')}\n")
                f.write(f"Number of formats: {len(results)}\n\n")
                
                for i, (chped_file, log_file, format_name) in enumerate(results):
                    f.write(f"Format {i+1}: {format_name}\n")
                    f.write(f"  - CHPED: {chped_file}\n")
                    f.write(f"  - Log: {log_file}\n")
                
                if self.start_time and self.end_time:
                    f.write(f"\nTotal execution time: {self.end_time - self.start_time:.2f} seconds\n")
                
                f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            print(f"📄 Summary saved to: {summary_file}")
    
    def run(self):
        """Main execution method."""
        try:
            # Load and validate configuration
            self.load_config()
            self.validate_config()
            
            # Print configuration summary
            if self.config.get('_verbose', True):
                self.print_configuration_summary()
            
            # Run NomenCleaner
            results = self.run_nomencleaner()
            
            # Print results summary
            if self.config.get('_verbose', True):
                self.print_results_summary(results)
            
            # Save summary
            self.save_summary(results)
            
            print(f"\n🎉 NomenCleaner completed successfully!")
            print(f"📊 Processed {len(results)} format(s)")
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False


def main():
    """Main function with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run NomenCleaner with YAML configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python src/tools/HATK/NomenCleaner/run_nomencleaner.py                                    # Use default config file
    python src/tools/HATK/NomenCleaner/run_nomencleaner.py my_config.yaml                     # Use custom config file
    python src/tools/HATK/NomenCleaner/run_nomencleaner.py --config nomencleaner_config.yaml  # Use --config flag
        """
    )
    
    parser.add_argument(
        'config_file', 
        nargs='?',
        default=None,
        help='Path to YAML configuration file (default: nomencleaner_run_config.yaml in NomenCleaner directory)'
    )
    
    parser.add_argument(
        '--config', '-c',
        dest='config_file_alt',
        help='Alternative way to specify config file'
    )
    
    parser.add_argument(
        '--verbose', '-v',
        action='store_true',
        help='Enable verbose output'
    )
    
    args = parser.parse_args()
    
    # Determine config file path
    config_path = args.config_file_alt if args.config_file_alt else args.config_file
    
    # Create and run NomenCleaner
    runner = NomenCleanerRunner(config_path)
    
    # Override verbose setting if specified
    if args.verbose:
        runner.config = runner.config or {}
        runner.config['_verbose'] = True
    
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
