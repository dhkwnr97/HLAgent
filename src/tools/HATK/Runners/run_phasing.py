#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_phasing.py
==============
BEAGLE Phasing execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the BEAGLE phasing
analysis with the specified parameters. It supports multiple input formats:
- VCF files
- PLINK files (.bed/.bim/.fam)
- BEAGLE files (.bgl)

The output includes:
- .bgl.phased file (phased BEAGLE format)
- .aa file (amino acid format for Omnibus Test)

Usage:
    python src/tools/HATK/Runners/run_phasing.py [config_file]
    
    If no config file is specified, it will look for 'phasing_run_config.yaml'
    in the current directory.

Author: HLAgent Development Team
Date: 2025
"""

import os
from dotenv import load_dotenv
import sys
import time
import yaml
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Union
from datetime import datetime
from shutil import which


load_dotenv()


# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

from src.tools.HATK.Phasing import HATK_Phasing


class PhasingRunner:
    """
    BEAGLE Phasing execution wrapper with YAML configuration support.
    """
    
    def __init__(self, config_f: str = None):
        # Get the directory containing this script
        current_dir = Path(__file__).parent
        
        # Set default config file if not provided
        if config_f is None:
            config_f = "phasing_run_config.yaml"
        
        # If config_f is not an absolute path, make it relative to the script directory
        if not os.path.isabs(config_f):
            self.config_path = os.path.join(current_dir, config_f)
        else:
            self.config_path = config_f
            
        self.config = {}
        self.start_time = None
        self.end_time = None
        self.phasing_instance = None
    
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
        required_params = ['_out']
        
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Required parameter '{param}' not found in configuration")
        
        # Check that at least one input format is specified
        input_formats = ['_bfile', '_vcf', '_bgl']
        if not any(self.config.get(param) for param in input_formats):
            raise ValueError("At least one input format must be specified: _bfile, _vcf, or _bgl")
        
        # Convert relative paths to absolute paths based on current working directory
        path_params = ['_out', '_bfile', '_vcf', '_bgl', '_markers']
        for param in path_params:
            if param in self.config and self.config[param]:
                if not os.path.isabs(self.config[param]):
                    self.config[param] = os.path.join(os.getcwd(), self.config[param])
        
        # Validate input files if enabled
        if self.config.get('_validation', {}).get('check_input_files', True):
            self._validate_input_files()
        
        # Validate BEAGLE version and threading compatibility
        self._validate_beagle_settings()
        
        return True
    
    def _validate_input_files(self):
        """Validate that input files exist."""
        # Check PLINK files
        if self.config.get('_bfile'):
            bfile_prefix = self.config['_bfile']
            required_extensions = ['.bed', '.bim', '.fam']
            
            for ext in required_extensions:
                if not os.path.exists(bfile_prefix + ext):
                    raise FileNotFoundError(f"Required PLINK file not found: {bfile_prefix}{ext}")
            
            print(f"✓ PLINK files validated: {bfile_prefix}[.bed, .bim, .fam]")
        
        # Check VCF file
        if self.config.get('_vcf'):
            vcf_file = self.config['_vcf']
            if not os.path.exists(vcf_file):
                raise FileNotFoundError(f"VCF file not found: {vcf_file}")
            print(f"✓ VCF file validated: {vcf_file}")
        
        # Check BEAGLE files
        if self.config.get('_bgl'):
            bgl_file = self.config['_bgl']
            if not os.path.exists(bgl_file):
                raise FileNotFoundError(f"BEAGLE file not found: {bgl_file}")
            print(f"✓ BEAGLE file validated: {bgl_file}")
            
            # Check markers file for BEAGLE input
            if self.config.get('_markers'):
                markers_file = self.config['_markers']
                if not os.path.exists(markers_file):
                    raise FileNotFoundError(f"Markers file not found: {markers_file}")
                print(f"✓ Markers file validated: {markers_file}")
    
    def _validate_beagle_settings(self):
        """Validate BEAGLE version and threading compatibility."""
        beagle_version = self.config.get('_beagle_compatibility', {}).get('version', '3.3.2')
        nthreads = self.config.get('_nthreads', 1)
        
        # Check for BEAGLE 3.3.2 multithreading issue
        if beagle_version == "3.3.2" and nthreads > 1:
            print(f"⚠️ Warning: BEAGLE 3.3.2 does not support multithreading.")
            print(f"   Current setting: _nthreads = {nthreads}")
            print(f"   BEAGLE 3.3.2 will use single thread regardless of this setting.")
            print(f"   BEAGLE with 4.x + version doesn't allow markers to have the same base position")
            print(f"   while HATK generates a bunch of markers which share the same base position.")
        
        print(f"✓ BEAGLE settings validated: version {beagle_version}, threads {nthreads}")
    
    def _determine_beagle_path(self) -> str:
        """Determine the correct BEAGLE path based on configuration."""
        beagle_version = self.config.get('_beagle_compatibility', {}).get('version', '3.3.2')
        
        if beagle_version == "bioconda":
            # Use system-installed BEAGLE via conda/bioconda
            beagle_path = which("beagle")
            if beagle_path is None:
                raise FileNotFoundError(
                    "BEAGLE not found in system PATH. "
                    "Please install BEAGLE via conda: 'conda install -c bioconda beagle'"
                )
            print(f"✓ Using system BEAGLE: {beagle_path}")
            return beagle_path
        
        elif beagle_version == "3.3.2":
            # Use local BEAGLE 3.3.2 jar file
            # Get the project root directory
            beagle_jar_path = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "src", "tools", "HATK", "dependency", "beagle.jar")
            
            if not os.path.exists(beagle_jar_path):
                raise FileNotFoundError(
                    f"BEAGLE 3.3.2 jar file not found: {beagle_jar_path}. "
                    "Please ensure beagle.jar is located in src/tools/HATK/dependency/"
                )
            
            # For jar files, we need to construct the java command
            java_path = which("java")
            if java_path is None:
                raise FileNotFoundError("Java not found in system PATH. Please install Java.")
            
            beagle_command = f"{java_path} -jar {beagle_jar_path}"
            print(f"✓ Using local BEAGLE 3.3.2 jar: {beagle_jar_path}")

            return beagle_command
        
        else:
            # Default to system BEAGLE for other versions
            beagle_path = which("beagle")
            if beagle_path is None:
                raise FileNotFoundError(
                    f"BEAGLE version '{beagle_version}' specified but beagle command not found in PATH. "
                    "Please install BEAGLE or use 'bioconda' or '3.3.2' as version."
                )
            print(f"✓ Using system BEAGLE for version {beagle_version}: {beagle_path}")
            return beagle_path
    
    def create_output_directory(self):
        """Create output directory and set up output file naming."""
        output_path = self.config.get('_out', 'data/output/Phasing')
        
        # Create output directory
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        
        # Generate descriptive output prefix based on input files
        input_basename = self._get_input_basename()
        
        # If output path doesn't include a filename, create one
        if os.path.isdir(output_path) or output_path.endswith('/'):
            output_prefix = os.path.join(output_path, f"phased_{input_basename}")
        else:
            output_prefix = output_path
        
        # Update config with generated output path
        self.config['_output_prefix'] = output_prefix
        
        if self.config.get('_verbose', True):
            print(f"📁 Output directory: {os.path.dirname(output_prefix)}")
            print(f"📄 Output prefix: {os.path.basename(output_prefix)}")
        
        return output_prefix
    
    def _get_input_basename(self) -> str:
        """Get a descriptive basename from input files."""
        if self.config.get('_bfile'):
            return os.path.basename(self.config['_bfile'])
        elif self.config.get('_vcf'):
            return os.path.basename(self.config['_vcf']).replace('.vcf', '').replace('.gz', '')
        elif self.config.get('_bgl'):
            return os.path.basename(self.config['_bgl']).replace('.bgl', '')
        else:
            return 'unknown'
    
    def print_configuration_summary(self):
        """Print a summary of the configuration."""
        print("\n" + "="*60)
        print("BEAGLE PHASING CONFIGURATION SUMMARY")
        print("="*60)
        
        # Input files
        if self.config.get('_bfile'):
            print(f"Input PLINK files:   {self.config['_bfile']}")
        if self.config.get('_vcf'):
            print(f"Input VCF file:      {self.config['_vcf']}")
        if self.config.get('_bgl'):
            print(f"Input BEAGLE file:   {self.config['_bgl']}")
            if self.config.get('_markers'):
                print(f"Markers file:        {self.config['_markers']}")
        
        print(f"Output prefix:       {self.config.get('_output_prefix', self.config.get('_out'))}")
        
        # Phasing parameters
        beagle_version = self.config.get('_beagle_compatibility', {}).get('version', '3.3.2')
        try:
            beagle_path = self._determine_beagle_path()
            print(f"BEAGLE version:      {beagle_version}")
            print(f"BEAGLE path:         {beagle_path}")
        except Exception as e:
            print(f"BEAGLE version:      {beagle_version}")
            print(f"BEAGLE path:         ERROR - {e}")
        
        print(f"Java memory:         {self.config.get('_java_mem', '2g')}")
        print(f"Number of threads:   {self.config.get('_nthreads', 1)}")
        print(f"Save intermediates:  {self.config.get('_save_intermediates', False)}")
        print(f"Generate AA file:    {self.config.get('_generate_aa', True)}")
        print(f"Verbose mode:        {self.config.get('_verbose', True)}")
        print("="*60)
    
    def run_analysis(self) -> Dict[str, Any]:
        """Run the BEAGLE phasing analysis.
        
        Returns:
            dict: Analysis results containing phased file paths and statistics
        """
        try:
            # Get output prefix
            output_prefix = self.config.get('_output_prefix', self.config.get('_out'))
            
            # Parse BEAGLE parameters
            beagle_params = self.config.get('_beagle_params', {})
            
            # Get BEAGLE version
            beagle_version = self.config.get('_beagle_compatibility', {}).get('version', '3.3.2')
            
            # Get region settings and missing value
            region_settings = self.config.get('_region_settings', {})
            chrom = str(region_settings.get('chr', 6))
            missing = str(self.config.get('_missing', '0'))
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.start_time = time.time()
            
            # Determine BEAGLE path based on configuration
            beagle_path = self._determine_beagle_path()
            
            # Initialize and run HATK_Phasing
            self.phasing_instance = HATK_Phasing(
                _out=output_prefix,
                _bfile=self.config.get('_bfile'),
                _vcf=self.config.get('_vcf'),
                _bgl=self.config.get('_bgl'),
                _markers=self.config.get('_markers'),
                _java_mem=self.config.get('_java_mem', '2g'),
                _nthreads=self.config.get('_nthreads', 1),
                _f_save_intermediates=self.config.get('_save_intermediates', False),
                _f_gzip=self.config.get('_gzip_output', True),
                _f_CookHLA_REF=self.config.get('_cookhla_ref', False),
                _beagle=beagle_path,
                _missing=self.config.get('_missing', '0'),
                beagle_version=beagle_version
            )
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.end_time = time.time()
            
            # Get results from the phasing instance
            results = {
                'bgl_phased': self.phasing_instance.bgl_phased,
                'input_format': self.phasing_instance.input_file_format,
                'beagle_version': beagle_version,
                'beagle_path': beagle_path
            }
            
            # Generate AA file if requested
            if self.config.get('_generate_aa', True):
                aa_file = self._generate_aa_file(results['bgl_phased'])
                results['aa_file'] = aa_file
            
            # Add execution statistics
            if self.start_time and self.end_time:
                results['execution_time'] = self.end_time - self.start_time
            
            # Add file size information
            if results['bgl_phased'] and os.path.exists(results['bgl_phased']):
                results['phased_file_size_mb'] = os.path.getsize(results['bgl_phased']) / (1024 * 1024)
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"BEAGLE phasing analysis failed: {e}")
    
    def _generate_aa_file(self, phased_file: str) -> str:
        """Generate amino acid (.aa) file from phased BEAGLE file.
        
        Args:
            phased_file: Path to the phased BEAGLE file
            
        Returns:
            str: Path to the generated .aa file
        """
        try:
            # Import the necessary module for AA file generation
            from src.tools.HATK.OmnibusTest import generate_aa_from_phased
            
            # Generate AA file
            output_prefix = self.config.get('_output_prefix', self.config.get('_out'))
            fam_file = self.config.get('_bfile') + '.fam' if self.config.get('_bfile') else None
            
            if not fam_file or not os.path.exists(fam_file):
                if self.config.get('_verbose', True):
                    print(f"⚠️ Warning: No .fam file available for AA file generation")
                return None

            if self.config.get('_verbose', True):
                print(f"🧬 Generating amino acid file from: {phased_file}")

            aa_file = generate_aa_from_phased(
                fam_file=fam_file,
                bgl_phased_file=phased_file,
                output_prefix=output_prefix,
                save_intermediates=self.config.get('_save_intermediates', False)
            )
            
            if self.config.get('_verbose', True):
                print(f"✓ AA file created: {aa_file}")
            
            return aa_file
                
        except Exception as e:
            if self.config.get('_verbose', True):
                print(f"⚠️ Warning: Could not generate AA file: {e}")
            return None
    
    def print_results_summary(self, results: Dict[str, Any]):
        """Print a summary of the phasing analysis results.
        
        Args:
            results: Analysis results dictionary
        """
        print("\n============================================================")
        print("BEAGLE PHASING RESULTS SUMMARY")
        print("============================================================\n")
        
        print("📊 Analysis Results:")
        print(f"   • Input format: {results.get('input_format', 'Unknown')}")
        print(f"   • BEAGLE version: {results.get('beagle_version', 'Unknown')}")
        
        if results.get('bgl_phased') and os.path.exists(results['bgl_phased']):
            print(f"   • Phased BEAGLE file: {results['bgl_phased']}")
            if results.get('phased_file_size_mb'):
                print(f"   • File size: {results['phased_file_size_mb']:.2f} MB")
        else:
            print(f"   • ❌ Phased file not found: {results.get('bgl_phased', 'N/A')}")
        
        if results.get('aa_file') and os.path.exists(results['aa_file']):
            print(f"   • Amino acid file: {results['aa_file']}")
        elif self.config.get('_generate_aa', True):
            print(f"   • ⚠️ AA file generation failed or skipped")
        
        print("\n📄 Output Files:")
        output_dir = os.path.dirname(self.config.get('_output_prefix', ''))
        if os.path.exists(output_dir):
            output_files = [f for f in os.listdir(output_dir) 
                          if f.startswith(os.path.basename(self.config.get('_output_prefix', '')))]
            for file in sorted(output_files):
                print(f"   • {os.path.join(output_dir, file)}")
        
        # Performance information
        if results.get('execution_time'):
            print(f"\n⏱️ Execution time: {results['execution_time']:.2f} seconds")
        
        print("\n✅ Phasing analysis complete!")
    
    def save_summary(self, results: Dict[str, Any]):
        """Save analysis summary to a file.
        
        Args:
            results: Analysis results dictionary
        """
        try:
            # Get the output prefix from config
            output_prefix = self.config.get('_output_prefix', self.config.get('_out'))
            
            # Create summary filename based on output prefix
            summary_filename = f"{os.path.basename(output_prefix)}_phasing_summary.txt"
            summary_path = os.path.join(os.path.dirname(output_prefix), summary_filename)
            
            with open(summary_path, 'w') as f:
                f.write("BEAGLE Phasing Analysis Summary\n")
                f.write("=" * 40 + "\n\n")
                
                # Configuration information
                f.write(f"Configuration file: {self.config_path}\n")
                
                # Input files
                if self.config.get('_bfile'):
                    f.write(f"Input PLINK files: {self.config['_bfile']}\n")
                if self.config.get('_vcf'):
                    f.write(f"Input VCF file: {self.config['_vcf']}\n")
                if self.config.get('_bgl'):
                    f.write(f"Input BEAGLE file: {self.config['_bgl']}\n")
                
                f.write(f"Output directory: {os.path.dirname(output_prefix)}\n\n")
                
                # Results
                f.write("Analysis Results:\n")
                f.write(f"  Input format: {results.get('input_format', 'Unknown')}\n")
                f.write(f"  BEAGLE version: {results.get('beagle_version', 'Unknown')}\n")
                
                f.write(f"\nOutput Files:\n")
                if results.get('bgl_phased'):
                    f.write(f"  Phased BEAGLE file: {results['bgl_phased']}\n")
                if results.get('aa_file'):
                    f.write(f"  Amino acid file: {results['aa_file']}\n")
                
                # Parameters
                f.write(f"\nPhasing Parameters:\n")
                beagle_version = self.config.get('_beagle_compatibility', {}).get('version', '3.3.2')
                f.write(f"  BEAGLE version: {beagle_version}\n")
                f.write(f"  Java memory: {self.config.get('_java_mem', '2g')}\n")
                f.write(f"  Threads: {self.config.get('_nthreads', 1)}\n")
                f.write(f"  Save intermediates: {self.config.get('_save_intermediates', False)}\n")
                
                # Execution time
                if results.get('execution_time'):
                    f.write(f"  Execution time: {results['execution_time']:.2f} seconds\n")
                
                f.write(f"\nTimestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            
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
            results = self.run_analysis()
            
            # Print results summary
            if self.config.get('_verbose', True):
                self.print_results_summary(results)
            
            # Save summary
            self.save_summary(results)
            
            print(f"\n🎉 BEAGLE phasing analysis completed successfully!")
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False


def main():
    """Main function with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run BEAGLE phasing analysis with YAML configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python src/tools/HATK/Runners/run_phasing.py                           # Use default config file
    python src/tools/HATK/Runners/run_phasing.py my_config.yaml            # Use custom config file
    python src/tools/HATK/Runners/run_phasing.py -c config.yaml -v         # Use config flag with verbose output
        """
    )
    
    parser.add_argument(
        'config_file', 
        nargs='?',
        default=None,
        help='Path to YAML configuration file (default: phasing_run_config.yaml)'
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
    
    # Create and run Phasing
    runner = PhasingRunner(config_path)
    
    # Override verbose setting if specified
    if args.verbose:
        runner.config = runner.config or {}
        runner.config['_verbose'] = True
    
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main() 