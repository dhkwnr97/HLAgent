#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
run_metaanalPlot.py
===================
Meta-analysis plot runner with YAML configuration support.

This script reads configuration from a YAML file and executes the meta-analysis
visualization (Q-Q, Manhattan, effect size, study comparison, forest, funnel plots)
using metaanalPlot.py's plotting functions.

Usage:
    python src/tools/HATK/Runners/run_metaanalPlot.py [config_file]
    
    If no config file is specified, it will look for 'metaanalPlot_run_config.yaml'
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

# Import plotting functions from metaanalPlot.py
from src.tools.HATK.Visualizer import metaanalPlot

class MetaAnalRunner:
    """
    Meta-analysis plot runner with YAML configuration support.
    """
    def __init__(self, config_file: str = None):
        current_dir = Path(__file__).parent
        if config_file is None:
            config_file = current_dir / "metaanalPlot_run_config.yaml"
        self.config_file = config_file
        self.config: Optional[Dict[str, Any]] = None
        self._load_config()
        self._setup_logging()

    def _load_config(self) -> None:
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            print(f"Configuration loaded from: {self.config_file}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Config file not found: {self.config_file}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML config file: {e}")

    def _setup_logging(self) -> None:
        logging_config = self.config.get('_logging', {})
        self.verbose = logging_config.get('verbose', True)

    def _log(self, message: str, level: str = "INFO") -> None:
        if self.verbose:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp} {level}]: {message}")

    def _validate_config(self) -> bool:
        try:
            required_params = ['_meta_file', '_output_prefix']
            for param in required_params:
                if param not in self.config:
                    raise ValueError(f"Required parameter missing in config: {param}")
            if not os.path.exists(self.config['_meta_file']):
                raise FileNotFoundError(f"Meta-analysis file not found: {self.config['_meta_file']}")
            output_dir = os.path.dirname(self.config['_output_prefix'])
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            self._log("Configuration validation successful")
            return True
        except (ValueError, FileNotFoundError) as e:
            self._log(f"Configuration validation failed: {e}", "ERROR")
            return False

    def run(self) -> bool:
        self._log("Starting Meta-Analysis Plot Runner")
        if not self._validate_config():
            return False
        try:
            meta_file = self.config['_meta_file']
            output_prefix = self.config['_output_prefix']
            plot_types = self.config.get('_plot_types', ["qq", "manhattan", "effect_dist", "study_comp", "forest", "funnel"])
            s1_logistic = self.config.get('_s1_logistic_result')
            s2_logistic = self.config.get('_s2_logistic_result')
            top_n_forest = self.config.get('_top_n_forest', 10)

            # Load meta-analysis results
            import pandas as pd
            meta_df = pd.read_csv(meta_file, sep=r'\s+')
            self._log(f"Loaded meta-analysis results: {len(meta_df)} variants")

            # Q-Q plot
            if "qq" in plot_types:
                metaanalPlot.plot_qq(meta_df, f"{output_prefix}_qq.png")
                self._log("Q-Q plot generated.")

            # Effect size distribution
            if "effect_dist" in plot_types:
                metaanalPlot.plot_effect_size_distribution(meta_df, f"{output_prefix}_effect_distribution.png")
                self._log("Effect size distribution plot generated.")

            # Funnel plot
            if "funnel" in plot_types:
                metaanalPlot.plot_funnel(meta_df, f"{output_prefix}_funnel.png")
                self._log("Funnel plot generated.")

            # Manhattan plot
            if "manhattan" in plot_types:
                if s1_logistic:
                    metaanalPlot.plot_manhattan(meta_df, s1_logistic, f"{output_prefix}_manhattan.png")
                    self._log("Manhattan plot generated.")
                else:
                    self._log("s1_logistic_result is required for Manhattan plot. Skipping.", "WARNING")

            # Study comparison plot
            if "study_comp" in plot_types:
                if s1_logistic and s2_logistic:
                    from src.tools.HATK.MetaAnalysis.metaanal_utils import read_logistic_result
                    s1_df = read_logistic_result(s1_logistic)
                    s2_df = read_logistic_result(s2_logistic)
                    metaanalPlot.plot_study_comparison(meta_df, s1_df, s2_df, f"{output_prefix}_study_comparison.png")
                    self._log("Study comparison plot generated.")
                else:
                    self._log("s1_logistic_result and s2_logistic_result are required for study comparison plot. Skipping.", "WARNING")

            # Forest plot
            if "forest" in plot_types:
                if s1_logistic and s2_logistic:
                    from src.tools.HATK.MetaAnalysis.metaanal_utils import read_logistic_result
                    s1_df = read_logistic_result(s1_logistic)
                    s2_df = read_logistic_result(s2_logistic)
                    metaanalPlot.plot_forest(meta_df, s1_df, s2_df, f"{output_prefix}_forest.png", top_n_forest)
                    self._log("Forest plot generated.")
                else:
                    self._log("s1_logistic_result and s2_logistic_result are required for forest plot. Skipping.", "WARNING")

            self._log("Meta-analysis plot generation completed successfully.")
            return True
        except Exception as e:
            self._log(f"Meta-analysis plot runner failed: {e}", "ERROR")
            import traceback
            traceback.print_exc()
            return False

def main():
    parser = argparse.ArgumentParser(
        description="Meta-analysis Plot Runner with YAML configuration.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        'config_file',
        nargs='?',
        default=None,
        help='Path to the YAML configuration file (default: metaanalPlot_run_config.yaml).'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate configuration without running the analysis.'
    )
    args = parser.parse_args()

    try:
        runner = MetaAnalRunner(args.config_file)
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