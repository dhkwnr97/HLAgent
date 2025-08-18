#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_bmarkerregression.py
=======================
SmartRegression execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the SmartRegression
analysis with the specified parameters.

Usage:
    python src/tools/HATK/Runners/run_bmarkerregression.py [config_file]
    
    If no config file is specified, it will look for 'bmarkerregression_run_config.yaml'
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
from typing import Dict, Any, List, Tuple, Union
from datetime import datetime

# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

from src.tools.HATK.bMarkerRegression.SmartRegression import SmartRegression


class BMarkerRegressionRunner:
    """
    SmartRegression execution wrapper with YAML configuration support.
    """
    
    def __init__(self, config_f: str = None):
        # Get the directory containing this script
        current_dir = Path(__file__).parent
        
        # Set default config file if not provided
        if config_f is None:
            config_f = "bmarkerregression_run_config.yaml"
        
        # If config_f is not an absolute path, make it relative to the script directory
        if not os.path.isabs(config_f):
            self.config_path = os.path.join(current_dir, config_f)
        else:
            self.config_path = config_f
            
        self.config = {}
        self.start_time = None
        self.end_time = None
        self.smart_reg = None
    
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
        required_params = ['_bfile_prefix', '_output_dir']
        
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Required parameter '{param}' not found in configuration")
        
        # Convert relative paths to absolute paths based on current working directory
        for param in ['_bfile_prefix', '_output_dir']:
            if not os.path.isabs(self.config[param]):
                self.config[param] = os.path.join(os.getcwd(), self.config[param])
        
        # Validate input files if enabled
        if self.config.get('_validation', {}).get('check_input_files', True):
            bfile_prefix = self.config['_bfile_prefix']
            required_extensions = ['.bed', '.bim', '.fam']
            
            for ext in required_extensions:
                if not os.path.exists(bfile_prefix + ext):
                    raise FileNotFoundError(f"Required file not found: {bfile_prefix}{ext}")
            
            print(f"✓ Input files validated")
            print(f"  - PLINK files: {bfile_prefix}[.bed, .bim, .fam]")
            
            # Validate phenotype file if specified
            if '_pheno_file' in self.config and self.config['_pheno_file']:
                pheno_file = self.config['_pheno_file']
                if not os.path.isabs(pheno_file):
                    pheno_file = os.path.join(os.getcwd(), pheno_file)
                if not os.path.exists(pheno_file):
                    raise FileNotFoundError(f"Phenotype file not found: {pheno_file}")
                print(f"  - Phenotype file: {pheno_file}")
            
            # Validate covariate file if specified
            if '_covar_file' in self.config and self.config['_covar_file']:
                covar_file = self.config['_covar_file']
                if not os.path.isabs(covar_file):
                    covar_file = os.path.join(os.getcwd(), covar_file)
                if not os.path.exists(covar_file):
                    raise FileNotFoundError(f"Covariate file not found: {covar_file}")
                print(f"  - Covariate file: {covar_file}")
        
        return True
    
    def create_output_directory(self):
        """Create output directory and set up output file naming."""
        output_dir = self.config.get('_output_dir', 'data/output/BMarkerRegression')
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output prefix based on input files
        bfile_prefix = self.config.get('_bfile_prefix', '')
        pheno_file = self.config.get('_pheno_file', '')
        
        # Extract base names
        bfile_basename = os.path.basename(bfile_prefix) if bfile_prefix else 'unknown'
        pheno_basename = os.path.basename(pheno_file).replace('.phe', '').replace('.txt', '') if pheno_file else 'fam_pheno'
        
        # Create descriptive output prefix
        output_prefix = f"{pheno_basename}_REG_{bfile_basename}"
        output_path = os.path.join(output_dir, output_prefix)
        
        # Update config with generated output path
        self.config['_output_prefix'] = output_path
        
        if self.config.get('_verbose', True):
            print(f"📁 Output directory: {output_dir}")
            print(f"📄 Output prefix: {output_prefix}")
        
        return output_path
    
    def print_configuration_summary(self):
        """Print a summary of the configuration."""
        print("\n" + "="*60)
        print("SMART REGRESSION CONFIGURATION SUMMARY")
        print("="*60)
        print(f"Input PLINK files:   {self.config['_bfile_prefix']}")
        print(f"Output directory:    {self.config['_output_dir']}")
        print(f"Phenotype file:      {self.config.get('_pheno_file', 'Using .fam file')}")
        print(f"Phenotype name:      {self.config.get('_pheno_name', 'N/A')}")
        print(f"Covariate file:      {self.config.get('_covar_file', 'N/A')}")
        print(f"Covariate names:     {self.config.get('_covar_names', [])}")
        print(f"Verbose mode:        {self.config.get('_logging', {}).get('verbose', True)}")
        print("="*60)
    
    def run_analysis(self) -> Tuple[str, Dict[str, Any]]:
        """Run the SmartRegression analysis.
        
        Returns:
            tuple: (association_file, summary_dict)
        """
        try:
            # Initialize SmartRegression with generated output prefix
            output_prefix = self.config.get('_output_prefix', self.config.get('_output_dir', 'data/output/BMarkerRegression'))
            
            self.smart_reg = SmartRegression(
                bfile_prefix=self.config.get('_bfile_prefix'),
                output_prefix=output_prefix,
                pheno_file=self.config.get('_pheno_file'),
                pheno_name=self.config.get('_pheno_name'),
                covar_file=self.config.get('_covar_file'),
                covar_names=self.config.get('_covar_names', []),
                condition_list=self.config.get('_condition_list'),
                chr=self.config.get('_chr', 6),
                from_mb=self.config.get('_from_mb', 29),
                to_mb=self.config.get('_to_mb', 34),
                ci=self.config.get('_ci', 0.95),
                verbose=self.config.get('_verbose', True)
            )
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.start_time = time.time()
            
            # Run complete analysis
            result_tuple = self.smart_reg.run_complete_analysis()
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.end_time = time.time()
            
            return result_tuple
            
        except Exception as e:
            raise RuntimeError(f"SmartRegression analysis failed: {e}")
    
    def print_results_summary(self, result_tuple):
        """Print a summary of the regression analysis results.
        
        Args:
            result_tuple (tuple): Tuple containing (assoc_file, summary_dict)
        """
        assoc_file, summary = result_tuple
        
        print("\n============================================================")
        print("SMART REGRESSION RESULTS SUMMARY")
        print("============================================================\n")
        
        print("📊 Analysis Statistics:")
        print(f"   • Association file: {assoc_file}")
        print(f"   • Regression type: {summary.get('regression_type', 'Unknown')}")
        print(f"   • Total variants: {summary.get('total_variants', 0):,}")
        print(f"   • Significant variants (P < 0.05): {summary.get('significant_variants', 0):,}")
        print(f"   • Highly significant variants (P < 5e-8): {summary.get('highly_significant_variants', 0):,}")
        
        if summary.get('hla_variants'):
            print("\n🧬 HLA-Specific Results:")
            print(f"   • HLA variants analyzed: {summary['hla_variants']:,}")
            print(f"   • Significant HLA variants (P < 5e-8): {summary.get('significant_hla_variants', 0):,}")
        
        print("\n📄 Output Files:")
        print(f"   • Association results: {assoc_file}")
        
        # Get the summary file path from our generated output prefix
        output_prefix = self.config.get('_output_prefix', self.config.get('_output_dir', 'data/output/BMarkerRegression'))
        summary_filename = f"{os.path.basename(output_prefix)}_summary.txt"
        summary_path = os.path.join(os.path.dirname(output_prefix), summary_filename)
        
        if os.path.exists(summary_path):
            print(f"   • Summary file: {summary_path}")
        else:
            print(f"   • Summary file: {summary_path} (not found)")
        
        # Also show the JSON summary file if it exists
        json_summary_path = summary.get('summary_file')
        if json_summary_path and os.path.exists(json_summary_path):
            print(f"   • JSON summary: {json_summary_path}")
        
        if summary.get('warnings'):
            print("\n⚠️ Warnings:")
            for warning in summary['warnings']:
                print(f"   • {warning}")
        
        print("\n✅ Analysis complete!")
    
    def save_summary(self, results: Dict[str, Any]):
        """Save analysis summary to a file.
        
        Args:
            results: Analysis results dictionary
        """
        try:
            # Get the output prefix from config
            output_prefix = self.config.get('_output_prefix', self.config.get('_output_dir', 'data/output/BMarkerRegression'))
            
            # Create summary filename based on output prefix
            summary_filename = f"{os.path.basename(output_prefix)}_summary.txt"
            summary_path = os.path.join(os.path.dirname(output_prefix), summary_filename)
            
            with open(summary_path, 'w') as f:
                f.write("SmartRegression Analysis Summary\n")
                f.write("=" * 40 + "\n\n")
                
                # Configuration information
                f.write(f"Configuration file: {self.config_path}\n")
                f.write(f"Input PLINK files: {self.config.get('_bfile_prefix')}\n")
                f.write(f"Output directory: {self.config.get('_output_dir')}\n")
                
                if self.config.get('_pheno_file'):
                    f.write(f"Phenotype file: {self.config.get('_pheno_file')}\n")
                else:
                    f.write("Phenotype source: .fam file\n")
                
                f.write(f"Regression type: {results.get('regression_type', 'Unknown')}\n\n")
                
                # Analysis statistics
                f.write("Analysis Statistics:\n")
                f.write(f"  Total variants: {results.get('total_variants', 0):,}\n")
                f.write(f"  Significant variants: {results.get('significant_variants', 0):,}\n")
                f.write(f"  HLA variants: {results.get('hla_variants', 0):,}\n\n")
                
                # Execution time
                if self.start_time and self.end_time:
                    execution_time = self.end_time - self.start_time
                    f.write(f"Total execution time: {execution_time:.2f} seconds\n")
                
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if self.config.get('_verbose', True):
                print(f"📄 Summary saved to: {summary_path}")
                
        except Exception as e:
            print(f"⚠️ Warning: Could not save summary file: {e}")
    
    def run(self):
        """Main execution method."""
        try:
            # Load and validate configuration
            self.load_config()
            self.validate_config()
            
            # Create output directory
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
            
            print(f"\n🎉 SmartRegression analysis completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False


def main():
    """Main function with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run SmartRegression analysis with YAML configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python src/tools/HATK/Runners/run_bmarkerregression.py                    # Use default config file
    python src/tools/HATK/Runners/run_bmarkerregression.py my_config.yaml     # Use custom config file
    python src/tools/HATK/Runners/run_bmarkerregression.py -c config.yaml -v  # Use config flag with verbose output
        """
    )
    
    parser.add_argument(
        'config_file', 
        nargs='?',
        default=None,
        help='Path to YAML configuration file (default: bmarkerregression_run_config.yaml)'
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
    
    # Create and run BMarkerRegression
    runner = BMarkerRegressionRunner(config_path)
    
    # Override verbose setting if specified
    if args.verbose:
        runner.config = runner.config or {}
        runner.config['_verbose'] = True
    
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()