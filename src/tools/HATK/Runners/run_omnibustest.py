#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_omnibustest.py
==================
OmnibusTest execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the Omnibus Test
analysis with the specified parameters. The Omnibus Test performs a likelihood
ratio test between null and alternative models for HLA amino acid analysis.

Usage:
    python src/tools/HATK/Runners/run_omnibustest.py [config_file]
    
    If no config file is specified, it will look for 'omnibustest_run_config.yaml'
    in the current directory.

Author: HLAgent Development Team
Date: 2025
"""

import os
import sys
import time
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from datetime import datetime

# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

# Import HATK modules
from src.tools.HATK.OmnibusTest.__main__ import HATK_OmibusTest


class OmnibusTestRunner:
    """
    OmnibusTest execution wrapper with YAML configuration support.
    """
    
    def __init__(self, config_f: str = None):
        # Get the directory containing this script
        current_dir = Path(__file__).parent
        
        # Set default config file if not provided
        if config_f is None:
            config_f = "omnibustest_run_config.yaml"
        
        # If config_f is not an absolute path, make it relative to the script directory
        if not os.path.isabs(config_f):
            self.config_path = os.path.join(current_dir, config_f)
        else:
            self.config_path = config_f
            
        self.config = {}
        self.start_time = None
        self.end_time = None
        self.omnibus_test = None

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
        # Required parameters
        required_params = ['_fam_file', '_pheno_file', '_pheno_name', '_out']
        
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Required parameter '{param}' not found in configuration")
        
        # Either _aa_file or _bgl_phased must be provided
        if not self.config.get('_aa_file') and not self.config.get('_bgl_phased'):
            raise ValueError("Either '_aa_file' or '_bgl_phased' must be provided in configuration")
        
        # Convert relative paths to absolute paths based on current working directory
        path_params = ['_fam_file', '_aa_file', '_bgl_phased', '_pheno_file', '_covar_file', '_condition_list', '_out']
        for param in path_params:
            if param in self.config and self.config[param]:
                if not os.path.isabs(self.config[param]):
                    self.config[param] = os.path.join(os.getcwd(), self.config[param])
        
        # Validate input files if enabled
        if self.config.get('_validation', {}).get('check_input_files', True):
            # Check FAM file
            if not os.path.exists(self.config['_fam_file']):
                raise FileNotFoundError(f"FAM file not found: {self.config['_fam_file']}")
            
            # Check phenotype file
            if not os.path.exists(self.config['_pheno_file']):
                raise FileNotFoundError(f"Phenotype file not found: {self.config['_pheno_file']}")
            
            # Check AA or BGL phased file
            if self.config.get('_aa_file'):
                if not os.path.exists(self.config['_aa_file']):
                    raise FileNotFoundError(f"AA file not found: {self.config['_aa_file']}")
            elif self.config.get('_bgl_phased'):
                if not os.path.exists(self.config['_bgl_phased']):
                    raise FileNotFoundError(f"BGL phased file not found: {self.config['_bgl_phased']}")
            
            # Check covariate file if specified
            if self.config.get('_covar_file') and not os.path.exists(self.config['_covar_file']):
                raise FileNotFoundError(f"Covariate file not found: {self.config['_covar_file']}")
            
            # Check condition list file if specified
            if self.config.get('_condition_list') and not os.path.exists(self.config['_condition_list']):
                raise FileNotFoundError(f"Condition list file not found: {self.config['_condition_list']}")
            
            print("✓ Input files validated")
            print(f"  - FAM file: {self.config['_fam_file']}")
            print(f"  - Phenotype file: {self.config['_pheno_file']}")
            if self.config.get('_aa_file'):
                print(f"  - AA file: {self.config['_aa_file']}")
            elif self.config.get('_bgl_phased'):
                print(f"  - BGL phased file: {self.config['_bgl_phased']}")
            
        return True

    def create_output_directory(self) -> str:
        """Create output directory and set up output file naming."""
        output_dir = self.config.get('_out', 'data/output/OmnibusTest')
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output prefix based on phenotype name
        pheno_name = self.config.get('_pheno_name', 'unknown')
        
        # Create descriptive output prefix
        output_prefix = f"omnibus_{pheno_name}"
        output_path = os.path.join(output_dir, output_prefix)
        
        # Update config with generated output path
        self.config['_output_prefix'] = output_path
        
        if self.config.get('_verbose', True):
            print(f"📁 Output directory: {output_dir}")
            print(f"📄 Output prefix: {output_prefix}")
        
        return output_path

    def parse_bfile_prefix(self) -> str:
        """Extract bfile prefix from FAM file path."""
        fam_file = self.config['_fam_file']
        if fam_file.endswith('.fam'):
            return fam_file[:-4]  # Remove .fam extension
        return fam_file

    def print_configuration_summary(self):
        """Print a summary of the configuration."""
        print("\n" + "="*60)
        print("OMNIBUS TEST CONFIGURATION SUMMARY")
        print("="*60)
        print(f"FAM file:            {self.config['_fam_file']}")
        
        if self.config.get('_aa_file'):
            print(f"AA file:             {self.config['_aa_file']}")
        elif self.config.get('_bgl_phased'):
            print(f"BGL phased file:     {self.config['_bgl_phased']}")
        
        print(f"Phenotype file:      {self.config['_pheno_file']}")
        print(f"Phenotype name:      {self.config['_pheno_name']}")
        
        if self.config.get('_covar_file'):
            print(f"Covariate file:      {self.config['_covar_file']}")
            print(f"Covariate names:     {self.config.get('_covar_name', 'N/A')}")
        
        if self.config.get('_condition'):
            print(f"Conditions:          {self.config['_condition']}")
        elif self.config.get('_condition_list'):
            print(f"Condition list:      {self.config['_condition_list']}")
        
        print(f"Output directory:    {self.config['_out']}")
        print(f"Save intermediates:  {self.config.get('_save_intermediates', False)}")
        print("="*60)

    def run_analysis(self) -> Tuple[Optional[str], Dict[str, Any]]:
        """Run the Omnibus Test analysis.
        
        Returns:
            tuple: (omnibus_result_file, summary_dict)
        """
        try:
            # Get bfile prefix from FAM file
            bfile_prefix = self.parse_bfile_prefix()
            
            # Process condition parameter if it's a comma-separated string
            condition = self.config.get('_condition')
            condition_list = self.config.get('_condition_list')
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.start_time = time.time()
            
            # Initialize and run OmnibusTest
            self.omnibus_test = HATK_OmibusTest(
                _out_prefix=self.config['_output_prefix'],
                _bfile=bfile_prefix,
                _pheno=self.config['_pheno_file'],
                _pheno_name=self.config['_pheno_name'],
                _aa=self.config.get('_aa_file'),
                _bgl_phased=self.config.get('_bgl_phased'),
                _covar=self.config.get('_covar_file'),
                _covar_name=self.config.get('_covar_name'),
                _condition=condition,
                _condition_list=condition_list,
                _f_save_intermediates=self.config.get('_save_intermediates', False)
            )
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.end_time = time.time()
            
            # Extract results
            omnibus_file = self.omnibus_test.OMNIBUS
            
            # Create summary dictionary
            summary = {
                'omnibus_result': omnibus_file,
                'phenotype': self.config['_pheno_name'],
                'pheno_file': self.config['_pheno_file'],
                'fam_file': self.config['_fam_file'],
                'aa_file': self.omnibus_test.aa,
                'conditions': condition if condition else 'None',
                'execution_time': self.end_time - self.start_time if self.start_time and self.end_time else None
            }
            
            return omnibus_file, summary
            
        except Exception as e:
            raise RuntimeError(f"OmnibusTest analysis failed: {e}")

    def print_results_summary(self, result_tuple: Tuple[str, Dict[str, Any]]):
        """Print a summary of the Omnibus Test results.
        
        Args:
            result_tuple: Tuple containing (omnibus_file, summary_dict)
        """
        omnibus_file, summary = result_tuple
        
        print("\n============================================================")
        print("OMNIBUS TEST RESULTS SUMMARY")
        print("============================================================\n")
        
        print("📊 Analysis Information:")
        print(f"   • Phenotype analyzed: {summary['phenotype']}")
        print(f"   • Conditions applied: {summary['conditions']}")
        print(f"   • Phenotype file: {os.path.basename(summary['pheno_file'])}")
        print(f"   • FAM file: {os.path.basename(summary['fam_file'])}")
        print(f"   • AA file used: {os.path.basename(summary['aa_file'])}")
        
        print("\n📄 Output Files:")
        print(f"   • Omnibus test results: {omnibus_file}")
        
        if os.path.exists(omnibus_file):
            # Count lines in result file
            with open(omnibus_file, 'r') as f:
                line_count = sum(1 for line in f) - 1  # Subtract header
            print(f"   • Number of tested positions: {line_count:,}")
        
        # Show summary file if it exists
        summary_file = omnibus_file.replace('.omnibus', '_summary.txt')
        if os.path.exists(summary_file):
            print(f"   • Summary file: {summary_file}")
        
        if summary.get('execution_time'):
            print(f"\n⏱️ Execution time: {summary['execution_time']:.2f} seconds")
        
        print("\n✅ Omnibus Test complete!")
        print("   The results show -log10(P-values) for each amino acid position.")
        print("   Higher values indicate stronger associations.")

    def save_summary(self, results: Dict[str, Any]):
        """Save analysis summary to a file.
        
        Args:
            results: Analysis results dictionary
        """
        try:
            omnibus_file = results['omnibus_result']
            summary_file = omnibus_file.replace('.omnibus', '_summary.txt')
            
            with open(summary_file, 'w') as f:
                f.write("Omnibus Test Analysis Summary\n")
                f.write("=" * 40 + "\n\n")
                
                # Configuration information
                f.write(f"Configuration file: {self.config_path}\n")
                f.write(f"FAM file: {results['fam_file']}\n")
                f.write(f"Phenotype file: {results['pheno_file']}\n")
                f.write(f"Phenotype name: {results['phenotype']}\n")
                f.write(f"AA file: {results['aa_file']}\n")
                f.write(f"Conditions: {results['conditions']}\n\n")
                
                # Analysis details
                f.write("Analysis Details:\n")
                f.write(f"  Output file: {omnibus_file}\n")
                
                if os.path.exists(omnibus_file):
                    with open(omnibus_file, 'r') as of:
                        lines = of.readlines()
                        if len(lines) > 1:
                            f.write(f"  Amino acid positions tested: {len(lines) - 1}\n")
                            
                            # Find top hits
                            data_lines = [l.strip().split() for l in lines[1:]]
                            if data_lines:
                                # Sort by log10_P (assuming it's the 4th column)
                                sorted_lines = sorted(data_lines, key=lambda x: float(x[3]), reverse=True)
                                f.write("\n  Top 5 associations:\n")
                                for i, line in enumerate(sorted_lines[:5]):
                                    f.write(f"    {i+1}. {line[0]} - log10_P: {line[3]}\n")
                
                if results.get('execution_time'):
                    f.write(f"\n  Execution time: {results['execution_time']:.2f} seconds\n")
                
                f.write(f"\nAnalysis completed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if self.config.get('_verbose', True):
                print(f"📄 Summary saved to: {summary_file}")
                
        except Exception as e:
            print(f"Warning: Could not save summary file: {e}")

    def run(self) -> bool:
        """Main execution method that orchestrates the entire analysis."""
        try:
            # Load configuration
            self.load_config()
            
            # Validate configuration
            self.validate_config()
            
            # Create output directory and set up file naming
            self.create_output_directory()
            
            # Print configuration summary
            if self.config.get('_verbose', True):
                self.print_configuration_summary()
            
            # Run analysis
            result_tuple = self.run_analysis()
            
            # Print results summary
            if self.config.get('_verbose', True):
                self.print_results_summary(result_tuple)
            
            # Save summary
            self.save_summary(result_tuple[1])
            
            print(f"\n🎉 Omnibus Test analysis completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            if self.config.get('_verbose', True):
                traceback.print_exc()
            return False


def main():
    """Main function with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run Omnibus Test analysis with YAML configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python src/tools/HATK/Runners/run_omnibustest.py                    # Use default config file
    python src/tools/HATK/Runners/run_omnibustest.py my_config.yaml     # Use custom config file
    python src/tools/HATK/Runners/run_omnibustest.py -c config.yaml -v  # Use config flag with verbose output

Notes:
    - The Omnibus Test requires phased data (either .aa file or .bgl.phased file)
    - Currently only supports Binary phenotypes
    - Conditioning requires phasing to be performed beforehand
        """
    )
    
    parser.add_argument(
        'config_file', 
        nargs='?',
        default=None,
        help='Path to YAML configuration file (default: omnibustest_run_config.yaml)'
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
    
    # Create and run OmnibusTest
    runner = OmnibusTestRunner(config_path)
    
    # Override verbose setting if specified
    if args.verbose:
        runner.config = runner.config or {}
        runner.config['_verbose'] = True
    
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
