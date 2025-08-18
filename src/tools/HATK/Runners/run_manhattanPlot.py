#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_manhattanPlot.py
====================
Manhattan Plot execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the Manhattan plot
generation with the specified parameters.

Usage:
    python src/tools/HATK/Runners/run_manhattanPlot.py [config_file]
    
    If no config file is specified, it will look for 'manhattanPlot_run_config.yaml'
    in the same directory as this script.

Author: HLAgent Development Team
Date: 2025
"""

import os
import sys
import yaml
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

# Add the project root directory to Python path
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

# Import the refactored plotting function
from src.tools.HATK.Visualizer.manhattanPlot import run_plot_generation


class ManhattanRunner:
    """
    Manhattan Plot execution wrapper with YAML configuration support.
    """
    
    def __init__(self, config_file: str = None):
        current_dir = Path(__file__).parent
        
        if config_file is None:
            config_file = current_dir / "manhattanPlot_run_config.yaml"
        
        self.config_file = config_file
        self.config: Optional[Dict[str, Any]] = None
        
        self._load_config()
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
        """Setup logging based on config."""
        logging_config = self.config.get('_logging', {})
        self.verbose = logging_config.get('verbose', True)

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log messages if verbose is enabled."""
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp} {level}]: {message}")
    
    def _validate_config(self) -> bool:
        """Validate required configuration parameters."""
        try:
            required_params = ['_input_file', '_output_dir', '_analysis_type']
            for param in required_params:
                if param not in self.config:
                    raise ValueError(f"Required parameter missing in config: {param}")
            
            input_file = self.config['_input_file']
            if not os.path.exists(input_file):
                raise FileNotFoundError(f"Input file not found: {input_file}")
            
            os.makedirs(self.config['_output_dir'], exist_ok=True)
            
            self._log("Configuration validation successful")
            return True
        except (ValueError, FileNotFoundError) as e:
            self._log(f"Configuration validation failed: {e}", "ERROR")
            return False

    def run(self) -> bool:
        """Main execution method."""
        self._log("Starting Manhattan Plot Runner")
        if not self._validate_config():
            return False

        try:
            # Prepare arguments for the plotting function
            viz_config = self.config.get('_visualization', {})
            
            args = argparse.Namespace(
                input=self.config['_input_file'],
                output=self.config['_output_dir'],
                type=self.config['_analysis_type'],
                format=viz_config.get('output_formats', ['html']),
                title=viz_config.get('title'),
                hla_region=viz_config.get('hla_region_focus', False),
                verbose=self.verbose,
            )

            # Run the plot generation
            self._log("Executing Manhattan plot generation...")
            run_plot_generation(args)
            self._log("Manhattan plot generation completed successfully.")
            return True

        except Exception as e:
            self._log(f"Manhattan plot runner failed: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return False


def main():
    """Main entry point for the runner script."""
    parser = argparse.ArgumentParser(
        description="Manhattan Plot Runner with YAML configuration.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'config_file',
        nargs='?',
        default=None,
        help='Path to the YAML configuration file (default: manhattanPlot_run_config.yaml).'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate configuration without running the analysis.'
    )
    args = parser.parse_args()

    try:
        runner = ManhattanRunner(args.config_file)
        
        if args.validate_only:
            if runner._validate_config():
                print("Configuration is valid.")
                return 0
            else:
                print("Configuration is invalid.")
                return 1
        
        success = runner.run()
        return 0 if success else 1

    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        return 1
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main()) 