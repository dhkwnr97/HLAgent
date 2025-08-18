#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_metaanal.py
===============
Meta-analysis execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the meta-analysis
of HLA association test results using inverse-variance weighting method.

Usage:
    python src/tools/HATK/Runners/run_metaanal.py [config_file]
    
    If no config file is specified, it will look for 'metaanal_run_config.yaml'
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
from typing import Dict, Any, Tuple
from datetime import datetime
# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

from src.tools.HATK.MetaAnalysis import run_meta_analysis, MetaAnalysisError


class MetaAnalysisRunner:
    """
    Meta-analysis execution wrapper with YAML configuration support.
    """
    
    def __init__(self, config_f: str = None):
        # Get the directory containing this script
        current_dir = Path(__file__).parent
        
        # Set default config file if not provided
        if config_f is None:
            config_f = "metaanal_run_config.yaml"
        
        # If config_f is not an absolute path, make it relative to the script directory
        if not os.path.isabs(config_f):
            self.config_path = os.path.join(current_dir, config_f)
        else:
            self.config_path = config_f
            
        self.config = {}
        self.start_time = None
        self.end_time = None
        self.result_df = None
        self.summary = None
    
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
        # Required parameters for meta-analysis
        required_params = ['_s1_logistic_result', '_s2_logistic_result', '_out']
        
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Required parameter '{param}' not found in configuration")
        
        # Convert relative paths to absolute paths
        path_params = ['_s1_logistic_result', '_s2_logistic_result', '_s1_bim', '_s2_bim', '_out']
        for param in path_params:
            if param in self.config and self.config[param] and not os.path.isabs(self.config[param]):
                self.config[param] = os.path.join(os.getcwd(), self.config[param])        
        # Validate input files if enabled
        if self.config.get('_validation', {}).get('check_input_files', True):
            # Check study 1 & 2 logistic result files
            if not os.path.exists(self.config['_s1_logistic_result']):
                raise FileNotFoundError(
                    f"Study 1 logistic result not found: {self.config['_s1_logistic_result']}")
            
            if not os.path.exists(self.config['_s2_logistic_result']):
                raise FileNotFoundError(
                    f"Study 2 logistic result not found: {self.config['_s2_logistic_result']}")
            
            print("✓ Input files validated")
            print(f"  - Study 1 logistic: {self.config['_s1_logistic_result']}")
            print(f"  - Study 2 logistic: {self.config['_s2_logistic_result']}")
            
            # Determine whether allele flipping will be applied
            use_flipping = self.config.get('_analysis_settings', {}).get('use_allele_flipping', False)

            if use_flipping:
                # When flipping is requested, BIM files must be present and valid
                for bim_key, study_name in [('_s1_bim', 'Study 1'), ('_s2_bim', 'Study 2')]:
                    if bim_key not in self.config or not self.config[bim_key]:
                        raise ValueError(
                            f"'{bim_key}' must be provided when use_allele_flipping is true")
                    if not os.path.exists(self.config[bim_key]):
                        raise FileNotFoundError(f"{study_name} BIM file not found: {self.config[bim_key]}")
                    print(f"  - {study_name} markers: {self.config[bim_key]}")
            else:
                # If flipping is disabled but BIM files were provided, warn the user they will be ignored
                if ('_s1_bim' in self.config and self.config['_s1_bim']) or (
                    '_s2_bim' in self.config and self.config['_s2_bim']):
                    print("ℹ️  BIM files supplied but 'use_allele_flipping' is false – they will be ignored.")
        
        return True    
    def create_output_directory(self):
        """Create output directory and set up output file naming."""
        output_dir = self.config.get('_out', 'data/output/MetaAnalysis')
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate output prefix based on config or input files
        if '_output_name' in self.config and self.config['_output_name']:
            output_name = self.config['_output_name']
        else:
            # Create descriptive output name from input files
            s1_basename = os.path.basename(self.config['_s1_logistic_result']).split('.')[0]
            s2_basename = os.path.basename(self.config['_s2_logistic_result']).split('.')[0]
            output_name = f"META_{s1_basename}_vs_{s2_basename}"
        
        output_path = os.path.join(output_dir, output_name)
        
        # Update config with generated output path
        self.config['_output_prefix'] = output_path
        
        if self.config.get('_verbose', True):
            print(f"📁 Output directory: {output_dir}")
            print(f"📄 Output prefix: {output_name}")
        
        return output_path    
    def print_configuration_summary(self):
        """Print a summary of the configuration."""
        print("\n" + "="*60)
        print("META-ANALYSIS CONFIGURATION SUMMARY")
        print("="*60)
        print(f"Study 1 logistic:    {self.config['_s1_logistic_result']}")
        print(f"Study 1 markers:     {self.config.get('_s1_bim', 'Not provided')}")
        print(f"Study 2 logistic:    {self.config['_s2_logistic_result']}")
        print(f"Study 2 markers:     {self.config.get('_s2_bim', 'Not provided')}")
        print(f"Allele flipping:     {self.config.get('_analysis_settings', {}).get('use_allele_flipping', False)}")
        print(f"Output directory:    {self.config['_out']}")
        print(f"Output name:         {self.config.get('_output_name', 'Auto-generated')}")
        print(f"Verbose mode:        {self.config.get('_verbose', True)}")
        print("="*60)
    
    def run_analysis(self) -> Tuple[Any, Dict[str, Any]]:
        """Run the meta-analysis.
        
        Returns:
            tuple: (result_dataframe, summary_dict)
        """
        try:
            if self.config.get('_performance', {}).get('measure_time', True):
                self.start_time = time.time()
            
            # Decide whether to pass BIM files based on 'use_allele_flipping'
            use_flipping = self.config.get('_analysis_settings', {}).get('use_allele_flipping', False)

            s1_bim = self.config.get('_s1_bim') if use_flipping else None
            s2_bim = self.config.get('_s2_bim') if use_flipping else None
            
            # Run meta-analysis
            result_df, summary = run_meta_analysis(
                study1_logistic=self.config['_s1_logistic_result'],
                study2_logistic=self.config['_s2_logistic_result'],
                study1_bim=s1_bim,
                study2_bim=s2_bim,
                output_prefix=self.config.get('_output_prefix')
            )
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.end_time = time.time()
            
            self.result_df = result_df
            self.summary = summary
            
            return result_df, summary
            
        except Exception as e:
            raise RuntimeError(f"Meta-analysis failed: {e}")
    
    def print_results_summary(self, result_df, summary):
        """Print a summary of the meta-analysis results.
        
        Args:
            result_df: Results DataFrame
            summary: Summary statistics dictionary
        """
        print("\n============================================================")
        print("META-ANALYSIS RESULTS SUMMARY")
        print("============================================================\n")
        
        print("📊 Analysis Statistics:")
        print(f"   • Study 1 variants: {summary.get('study1_variants', 0):,}")
        print(f"   • Study 2 variants: {summary.get('study2_variants', 0):,}")
        print(f"   • Common variants: {summary.get('common_variants', 0):,}")
        print(f"   • Analyzed variants: {summary.get('analyzed_variants', 0):,}")
        print(f"   • Significant variants (P < 0.05): {summary.get('significant_variants', 0):,}")
        print(f"   • Highly significant variants (P < 5e-8): {summary.get('highly_significant_variants', 0):,}")
        
        if len(result_df) > 0:
            # Find top hits
            top_hits = result_df.nsmallest(5, 'MetaP')
            if len(top_hits) > 0:
                print("\n🎯 Top 5 associations:")
                for idx, hit in top_hits.iterrows():
                    print(f"   • {hit['SNP']}: P = {hit['MetaP']:.2e}, Beta = {hit['BETA']:.4f}, SE = {hit['SE']:.4f}")
        
        print("\n📄 Output Files:")
        if 'output_file' in summary:
            print(f"   • Meta-analysis results: {summary['output_file']}")
        
        # Summary file path
        summary_path = f"{self.config.get('_output_prefix')}_summary.txt"
        if os.path.exists(summary_path):
            print(f"   • Summary file: {summary_path}")
        
        print("\n✅ Meta-analysis complete!")
    
    def save_summary(self, summary: Dict[str, Any]):
        """Save analysis summary to a file.
        
        Args:
            summary: Analysis summary dictionary
        """
        try:
            summary_path = f"{self.config.get('_output_prefix')}_summary.txt"            
            with open(summary_path, 'w') as f:
                f.write("Meta-Analysis Summary\n")
                f.write("=" * 40 + "\n\n")
                
                # Configuration information
                f.write(f"Configuration file: {self.config_path}\n")
                f.write(f"Study 1 logistic: {self.config.get('_s1_logistic_result')}\n")
                f.write(f"Study 1 markers: {self.config.get('_s1_bim', 'Not provided')}\n")
                f.write(f"Study 2 logistic: {self.config.get('_s2_logistic_result')}\n")
                f.write(f"Study 2 markers: {self.config.get('_s2_bim', 'Not provided')}\n")
                f.write(f"Output directory: {self.config.get('_out')}\n\n")
                
                # Analysis statistics
                f.write("Analysis Statistics:\n")
                f.write(f"  Study 1 variants: {summary.get('study1_variants', 0):,}\n")
                f.write(f"  Study 2 variants: {summary.get('study2_variants', 0):,}\n")
                f.write(f"  Common variants: {summary.get('common_variants', 0):,}\n")
                f.write(f"  Analyzed variants: {summary.get('analyzed_variants', 0):,}\n")
                f.write(f"  Significant variants (P < 0.05): {summary.get('significant_variants', 0):,}\n")
                f.write(f"  Highly significant variants (P < 5e-8): {summary.get('highly_significant_variants', 0):,}\n\n")
                
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
            result_df, summary = self.run_analysis()
            
            # Print results summary
            if self.config.get('_verbose', True):
                self.print_results_summary(result_df, summary)
            
            # Save summary
            self.save_summary(summary)
            
            print(f"\n🎉 Meta-analysis completed successfully!")
            return True            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False


def main():
    """Main function with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run HLA meta-analysis with YAML configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python src/tools/HATK/Runners/run_metaanal.py                    # Use default config file
    python src/tools/HATK/Runners/run_metaanal.py my_config.yaml     # Use custom config file
    python src/tools/HATK/Runners/run_metaanal.py -c config.yaml -v  # Use config flag with verbose output
        """
    )
    
    parser.add_argument(
        'config_file', 
        nargs='?',
        default=None,
        help='Path to YAML configuration file (default: metaanal_run_config.yaml)'
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
    
    # Create and run MetaAnalysis
    runner = MetaAnalysisRunner(config_path)
    
    # Override verbose setting if specified
    if args.verbose:
        runner.config = runner.config or {}
        runner.config['_verbose'] = True
    
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()