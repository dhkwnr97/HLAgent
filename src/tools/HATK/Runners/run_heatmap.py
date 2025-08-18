#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_heatmapPlot.py
==================
HLA Heatmap execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the HLA heatmap
generation with the specified parameters.

Usage:
    python src/tools/HATK/Runners/run_heatmapPlot.py [config_file]
    
    If no config file is specified, it will look for 'heatmap_run_config.yaml'
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
from typing import Dict, Any, List, Tuple, Union, Optional
from datetime import datetime

# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

# Import the heatmap module (will be created)
from src.tools.HATK.Visualizer.heatmapPlot import HeatmapGenerator


class HeatmapRunner:
    """
    HLA Heatmap execution wrapper with YAML configuration support.
    """
    
    def __init__(self, config_file: str = None):
        # Get the directory containing this script
        current_dir = Path(__file__).parent
        
        # Set default config file if not provided
        if config_file is None:
            config_file = "heatmap_run_config.yaml"
        
        # Convert to absolute path if relative
        if not os.path.isabs(config_file):
            config_file = current_dir / config_file
        
        self.config_file = config_file
        self.config = None
        self.results = {}
        
        # Load configuration
        self._load_config()
        
        # Initialize logging
        self._setup_logging()
    
    def _load_config(self) -> None:
        """Load configuration from YAML file."""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            print(f"Configuration loaded from: {self.config_file}")
            
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML config file: {e}")
    
    def _setup_logging(self) -> None:
        """Setup logging configuration."""
        self.verbose = self.config.get('_logging', {}).get('verbose', True)
        self.log_level = self.config.get('_logging', {}).get('log_level', 'INFO')
        self.show_progress = self.config.get('_logging', {}).get('show_progress', True)
    
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log messages with timestamp."""
        if not self.verbose:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if level == "ERROR":
            print(f"[{timestamp} ERROR]: {message}")
        elif level == "WARNING":
            print(f"[{timestamp} WARNING]: {message}")
        else:
            print(f"[{timestamp} INFO]: {message}")
    
    def _validate_config(self) -> bool:
        """Validate configuration parameters."""
        try:
            # Check required parameters
            required_params = ['_assoc_file', '_maptable_dir', '_output_dir', '_hla_genes', '_imgt_version']
            
            for param in required_params:
                if param not in self.config:
                    raise ValueError(f"Required parameter missing: {param}")
            
            # Validate file paths
            assoc_file = self.config['_assoc_file']
            if not os.path.exists(assoc_file):
                raise FileNotFoundError(f"Association file not found: {assoc_file}")
            
            maptable_dir = self.config['_maptable_dir']
            if not os.path.isdir(maptable_dir):
                raise FileNotFoundError(f"Maptable directory not found: {maptable_dir}")
            
            # Validate HLA genes
            hla_genes = self.config['_hla_genes']
            if not isinstance(hla_genes, list) or len(hla_genes) == 0:
                raise ValueError("_hla_genes must be a non-empty list")
            
            # Check maptable files exist
            imgt_version = self.config['_imgt_version']
            genome_build = self.config.get('_genome_build', 'hg18')
            
            missing_maptables = []
            for hla_gene in hla_genes:
                maptable_file = os.path.join(
                    maptable_dir, 
                    f"HLA_MAPTABLE_{hla_gene}.{genome_build}.imgt{imgt_version}.txt"
                )
                if not os.path.exists(maptable_file):
                    missing_maptables.append(maptable_file)
            
            if missing_maptables:
                raise FileNotFoundError(f"Missing maptable files: {missing_maptables}")
            
            # Create output directory if it doesn't exist
            output_dir = self.config['_output_dir']
            os.makedirs(output_dir, exist_ok=True)
            
            self._log("Configuration validation successful")
            return True
            
        except Exception as e:
            self._log(f"Configuration validation failed: {str(e)}", "ERROR")
            return False
    
    def _get_maptable_path(self, hla_gene: str) -> str:
        """Get the full path to maptable file for a specific HLA gene."""
        maptable_dir = self.config['_maptable_dir']
        imgt_version = self.config['_imgt_version']
        genome_build = self.config.get('_genome_build', 'hg18')
        
        maptable_file = f"HLA_MAPTABLE_{hla_gene}.{genome_build}.imgt{imgt_version}.txt"
        return os.path.join(maptable_dir, maptable_file)
    
    def _get_output_prefix(self, hla_gene: str) -> str:
        """Get the output file prefix for a specific HLA gene."""
        output_dir = self.config['_output_dir']
        return os.path.join(output_dir, f"heatmap_{hla_gene}")
    
    def run_single_heatmap(self, hla_gene: str) -> Optional[str]:
        """Run heatmap generation for a single HLA gene."""
        try:
            self._log(f"Starting heatmap generation for HLA-{hla_gene}")
            
            # Get file paths
            assoc_file = self.config['_assoc_file']
            maptable_file = self._get_maptable_path(hla_gene)
            output_prefix = self._get_output_prefix(hla_gene)
            
            # Get visualization settings
            viz_config = self.config.get('_visualization', {})
            use_plotly = viz_config.get('use_plotly', True)
            save_intermediates = viz_config.get('save_intermediates', True)
            
            # Create heatmap generator
            generator = HeatmapGenerator(
                assoc_file=assoc_file,
                maptable_file=maptable_file,
                hla_gene=hla_gene,
                output_prefix=output_prefix,
                use_plotly=use_plotly,
                save_intermediates=save_intermediates,
                config=self.config,
                verbose=self.verbose
            )
            
            # Generate heatmap
            result = generator.generate()
            
            if result:
                self._log(f"Heatmap generation completed for HLA-{hla_gene}: {result}")
                return result
            else:
                self._log(f"Heatmap generation failed for HLA-{hla_gene}", "ERROR")
                return None
                
        except Exception as e:
            self._log(f"Error generating heatmap for HLA-{hla_gene}: {str(e)}", "ERROR")
            
            # Continue on error if configured
            if self.config.get('_error_handling', {}).get('continue_on_error', True):
                return None
            else:
                raise
    
    def run_all_heatmaps(self) -> Dict[str, Optional[str]]:
        """Run heatmap generation for all configured HLA genes."""
        results = {}
        hla_genes = self.config['_hla_genes']
        
        self._log(f"Starting heatmap generation for {len(hla_genes)} HLA genes: {hla_genes}")
        
        start_time = time.time()
        
        for i, hla_gene in enumerate(hla_genes, 1):
            if self.show_progress:
                self._log(f"Processing HLA gene {i}/{len(hla_genes)}: {hla_gene}")
            
            result = self.run_single_heatmap(hla_gene)
            results[hla_gene] = result
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Summary
        successful = sum(1 for result in results.values() if result is not None)
        failed = len(hla_genes) - successful
        
        self._log(f"Heatmap generation completed in {elapsed_time:.2f} seconds")
        self._log(f"Summary: {successful} successful, {failed} failed")
        
        if successful > 0:
            self._log("Successful heatmaps:")
            for hla_gene, result in results.items():
                if result:
                    self._log(f"  HLA-{hla_gene}: {result}")
        
        if failed > 0:
            self._log("Failed heatmaps:", "WARNING")
            for hla_gene, result in results.items():
                if not result:
                    self._log(f"  HLA-{hla_gene}: Failed", "WARNING")
        
        self.results = results
        return results
    
    def run(self) -> bool:
        """Main execution method."""
        try:
            self._log("Starting HLA Heatmap Runner")
            self._log(f"Configuration file: {self.config_file}")
            
            # Validate configuration
            if not self._validate_config():
                return False
            
            # Run heatmap generation
            results = self.run_all_heatmaps()
            
            # Check if any heatmaps were generated successfully
            successful_count = sum(1 for result in results.values() if result is not None)
            
            if successful_count > 0:
                self._log("Heatmap generation completed successfully")
                return True
            else:
                self._log("No heatmaps were generated successfully", "ERROR")
                return False
                
        except Exception as e:
            self._log(f"Heatmap runner failed: {str(e)}", "ERROR")
            return False


def create_argument_parser() -> argparse.ArgumentParser:
    """Create command-line argument parser."""
    parser = argparse.ArgumentParser(
        description="HLA Heatmap Runner with YAML configuration",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument(
        'config_file',
        nargs='?',
        default='heatmap_run_config.yaml',
        help='Path to YAML configuration file (default: heatmap_run_config.yaml)'
    )
    
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate configuration without running analysis'
    )
    
    parser.add_argument(
        '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    
    return parser


def main() -> int:
    """Main entry point."""
    try:
        parser = create_argument_parser()
        args = parser.parse_args()
        
        # Create runner
        runner = HeatmapRunner(args.config_file)
        
        # Override verbosity if specified
        if args.verbose:
            runner.verbose = True
        
        # Validate only mode
        if args.validate_only:
            if runner._validate_config():
                print("Configuration validation successful")
                return 0
            else:
                print("Configuration validation failed")
                return 1
        
        # Run heatmap generation
        success = runner.run()
        
        return 0 if success else 1
        
    except KeyboardInterrupt:
        print("\nOperation cancelled by user")
        return 1
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
