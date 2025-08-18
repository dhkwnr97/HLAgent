#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_bmarkerstepwiseregression.py
===============================
Stepwise Conditional Regression execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the Enhanced Stepwise
Conditional Regression analysis with the specified parameters.

Usage:
    python src/tools/HATK/Runners/run_bmarkerstepwiseregression.py [config_file]
    
    If no config file is specified, it will look for 'bmarkerstepwiseregression_run_config.yaml'
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

from src.tools.HATK.bMarkerStepwiseRegression.StepCon_SmartRegression import StepwiseConditionalRegression


class BMarkerStepwiseRegressionRunner:
    """
    Enhanced Stepwise Conditional Regression execution wrapper with YAML configuration support.
    """
    
    def __init__(self, config_f: str = None):
        # Get the directory containing this script
        current_dir = Path(__file__).parent
        
        # Set default config file if not provided
        if config_f is None:
            config_f = "bmarkerstepwiseregression_run_config.yaml"
        
        # If config_f is not an absolute path, make it relative to the script directory
        if not os.path.isabs(config_f):
            self.config_path = os.path.join(current_dir, config_f)
        else:
            self.config_path = config_f
            
        self.config = {}
        self.start_time = None
        self.end_time = None
        self.stepwise_reg = None
    
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
        required_params = ['_bfile_prefix', '_out']
        
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Required parameter '{param}' not found in configuration")
        
        # Convert relative paths to absolute paths based on current working directory
        for param in ['_bfile_prefix', '_out']:
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
        output_dir = self.config.get('_out', 'data/output/BMarkerStepwiseRegression')
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output prefix based on input files
        bfile_prefix = self.config.get('_bfile_prefix', '')
        pheno_file = self.config.get('_pheno_file', '')
        
        # Extract base names
        bfile_basename = os.path.basename(bfile_prefix) if bfile_prefix else 'unknown'
        pheno_basename = os.path.basename(pheno_file).replace('.phe', '').replace('.txt', '') if pheno_file else 'fam_pheno'
        
        # Create descriptive output prefix
        output_prefix = f"{pheno_basename}_STEPWISE_{bfile_basename}"
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
        print("STEPWISE CONDITIONAL REGRESSION CONFIGURATION SUMMARY")
        print("="*60)
        print(f"Input PLINK files:   {self.config['_bfile_prefix']}")
        print(f"Output directory:    {self.config['_out']}")
        print(f"Phenotype file:      {self.config.get('_pheno_file', 'Using .fam file')}")
        print(f"Phenotype name:      {self.config.get('_pheno_name', 'N/A')}")
        print(f"Covariate file:      {self.config.get('_covar_file', 'N/A')}")
        print(f"Covariate names:     {self.config.get('_covar_names', [])}")
        print(f"Significance threshold: {self.config.get('_significance_threshold', 0.05)}")
        print(f"GWAS threshold:      {self.config.get('_genome_wide_threshold', 5e-8)}")
        print(f"Max iterations:      {self.config.get('_max_iterations', 100)}")
        print(f"HLA region:          {self.config.get('_hla_region', True)}")
        print(f"Verbose mode:        {self.config.get('_verbose', True)}")
        print("="*60)
    
    def run_analysis(self) -> Dict[str, Any]:
        """Run the Stepwise Conditional Regression analysis.
        
        Returns:
            Dict[str, Any]: Analysis results
        """
        try:
            # Initialize Stepwise Conditional Regression with generated output prefix
            output_prefix = self.config.get('_output_prefix', self.config.get('_out', 'data/output/BMarkerStepwiseRegression'))
            
            self.stepwise_reg = StepwiseConditionalRegression(
                bfile_prefix=self.config.get('_bfile_prefix'),
                output_prefix=output_prefix,
                pheno_file=self.config.get('_pheno_file'),
                pheno_name=self.config.get('_pheno_name'),
                covar_file=self.config.get('_covar_file'),
                covar_names=self.config.get('_covar_names', []),
                plink_path=self.config.get('_plink_path', 'plink'),
                significance_threshold=self.config.get('_significance_threshold', 0.05),
                genome_wide_threshold=self.config.get('_genome_wide_threshold', 5e-8),
                max_iterations=self.config.get('_max_iterations', 100),
                chr_filter=self.config.get('_chr', 6),
                from_mb=self.config.get('_from_mb', 29),
                to_mb=self.config.get('_to_mb', 34),
                hla_region=self.config.get('_hla_region', True),
                verbose=self.config.get('_verbose', True)
            )
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.start_time = time.time()
            
            # Run stepwise analysis
            results = self.stepwise_reg.run_stepwise_analysis()
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.end_time = time.time()
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"Stepwise Conditional Regression analysis failed: {e}")
    
    def print_results_summary(self, results: Dict[str, Any]):
        """Print a summary of the stepwise regression analysis results.
        
        Args:
            results: Analysis results dictionary
        """
        print("\n============================================================")
        print("STEPWISE CONDITIONAL REGRESSION RESULTS SUMMARY")
        print("============================================================\n")
        
        print("📊 Analysis Statistics:")
        print(f"   • Analysis type: {results.get('analysis_type', 'Unknown')}")
        print(f"   • Regression type: {results.get('regression_type', 'Unknown')}")
        print(f"   • Phenotype type: {results.get('phenotype_type', 'Unknown')}")
        print(f"   • Total iterations: {results.get('total_iterations', 0)}")
        print(f"   • Selected SNPs: {results.get('n_selected_snps', 0)}")
        print(f"   • Execution time: {results.get('execution_time', 0):.2f} seconds")
        
        if results.get('analysis_region', {}).get('hla_region'):
            region = results['analysis_region']
            print(f"\n🧬 Analysis Region:")
            print(f"   • HLA region: Chr{region.get('chromosome', 6)}:{region.get('from_mb', 29)}-{region.get('to_mb', 34)}Mb")
        
        if results.get('selected_snps'):
            print(f"\n🎯 Selected SNPs:")
            for i, snp in enumerate(results['selected_snps'][:10], 1):  # Show top 10
                print(f"   {i:2d}. {snp}")
            if len(results['selected_snps']) > 10:
                print(f"   ... and {len(results['selected_snps']) - 10} more")
        
        print("\n📄 Output Files:")
        output_prefix = self.config.get('_output_prefix', self.config.get('_out', 'data/output/BMarkerStepwiseRegression'))
        
        # List expected output files
        expected_files = [
            f"{os.path.basename(output_prefix)}_stepwise_summary.json",
            f"{os.path.basename(output_prefix)}_selected_snps.txt",
            f"{os.path.basename(output_prefix)}_iteration_history.csv"
        ]
        
        for filename in expected_files:
            filepath = os.path.join(os.path.dirname(output_prefix), filename)
            if os.path.exists(filepath):
                print(f"   • {filename}: ✓")
            else:
                print(f"   • {filename}: ✗ (not found)")
        
        print("\n✅ Stepwise analysis complete!")
    
    def save_summary(self, results: Dict[str, Any]):
        """Save analysis summary to a file.
        
        Args:
            results: Analysis results dictionary
        """
        try:
            # Get the output prefix from config
            output_prefix = self.config.get('_output_prefix', self.config.get('_out', 'data/output/BMarkerStepwiseRegression'))
            
            # Create summary filename based on output prefix
            summary_filename = f"{os.path.basename(output_prefix)}_runner_summary.txt"
            summary_path = os.path.join(os.path.dirname(output_prefix), summary_filename)
            
            with open(summary_path, 'w') as f:
                f.write("Stepwise Conditional Regression Analysis Summary\n")
                f.write("=" * 60 + "\n\n")
                
                # Configuration information
                f.write(f"Configuration file: {self.config_path}\n")
                f.write(f"Input PLINK files: {self.config.get('_bfile_prefix')}\n")
                f.write(f"Output directory: {self.config.get('_out')}\n")
                
                if self.config.get('_pheno_file'):
                    f.write(f"Phenotype file: {self.config.get('_pheno_file')}\n")
                else:
                    f.write("Phenotype source: .fam file\n")
                
                f.write(f"Regression type: {results.get('regression_type', 'Unknown')}\n")
                f.write(f"Phenotype type: {results.get('phenotype_type', 'Unknown')}\n\n")
                
                # Analysis statistics
                f.write("Analysis Statistics:\n")
                f.write(f"  Total iterations: {results.get('total_iterations', 0)}\n")
                f.write(f"  Selected SNPs: {results.get('n_selected_snps', 0)}\n")
                f.write(f"  Significance threshold: {results.get('significance_threshold', 0.05)}\n")
                f.write(f"  Genome-wide threshold: {results.get('genome_wide_threshold', 5e-8)}\n\n")
                
                # Selected SNPs
                if results.get('selected_snps'):
                    f.write("Selected SNPs:\n")
                    for i, snp in enumerate(results['selected_snps'], 1):
                        f.write(f"  {i:2d}. {snp}\n")
                    f.write("\n")
                
                # Execution time
                if self.start_time and self.end_time:
                    execution_time = self.end_time - self.start_time
                    f.write(f"Total execution time: {execution_time:.2f} seconds\n")
                
                f.write(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            if self.config.get('_verbose', True):
                print(f"📄 Runner summary saved to: {summary_path}")
                
        except Exception as e:
            print(f"⚠️ Warning: Could not save runner summary file: {e}")
    
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
            results = self.run_analysis()
            
            # Print results summary
            if self.config.get('_verbose', True):
                self.print_results_summary(results)
            
            # Save summary
            self.save_summary(results)
            
            # Cleanup if requested
            if self.config.get('_temp_files', {}).get('cleanup_on_exit', True):
                if self.stepwise_reg:
                    self.stepwise_reg.cleanup_intermediate_files()
            
            print(f"\n🎉 Stepwise Conditional Regression analysis completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False


def main():
    """Main function with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run Stepwise Conditional Regression analysis with YAML configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python src/tools/HATK/Runners/run_bmarkerstepwiseregression.py                           # Use default config file
    python src/tools/HATK/Runners/run_bmarkerstepwiseregression.py my_config.yaml          # Use custom config file
    python src/tools/HATK/Runners/run_bmarkerstepwiseregression.py -c config.yaml -v       # Use config flag with verbose output
        """
    )
    
    parser.add_argument(
        'config_file', 
        nargs='?',
        default=None,
        help='Path to YAML configuration file (default: bmarkerstepwiseregression_run_config.yaml)'
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
    
    # Create and run BMarkerStepwiseRegression
    runner = BMarkerStepwiseRegressionRunner(config_path)
    
    # Override verbose setting if specified
    if args.verbose:
        runner.config = runner.config or {}
        runner.config['_verbose'] = True
    
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
