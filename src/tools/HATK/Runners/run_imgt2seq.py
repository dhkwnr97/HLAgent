#!/usr/bin/env python3
"""
IMGT2Seq Runner Script
======================

This script runs the IMGT2Seq function with parameters from the YAML configuration file.
"""

import os
import sys
import yaml
from pathlib import Path

# Add project root to Python path
project_root = str(Path(__file__).parents[4])  # Go up 4 levels to reach project root
if project_root not in sys.path:
    sys.path.append(project_root)

from src.tools.HATK.IMGT2Seq import IMGT2Seq


class IMGT2SeqRunner:
    """
    IMGT2Seq execution wrapper with YAML configuration support.
    """
    def __init__(self, config_f: str = None):
        current_dir = Path(__file__).parent
        if config_f is None:
            config_f = "imgt2seq_run_config.yaml"
        if not os.path.isabs(config_f):
            self.config_path = os.path.join(current_dir, config_f)
        else:
            self.config_path = config_f
        self.config = {}
        self.result = None

    def load_config(self):
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r') as f:
                self.config = yaml.safe_load(f)
            print(f"✓ Configuration loaded from: {self.config_path}")
            return self.config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")

    def validate_config(self):
        """Validate the configuration parameters."""
        required_params = [
            '_imgt', '_hg', '_out_dir', '_imgt_dir', '_no_Indel', '_MultiP',
            '_f_save_intermediates', '_no_prime', '_p_data', '__Nfield_OUTPUT_FORMAT', '_HLA_target'
        ]
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Required parameter '{param}' not found in configuration")
        # Convert relative output dir to absolute
        if not os.path.isabs(self.config['_out_dir']):
            self.config['_out_dir'] = os.path.abspath(self.config['_out_dir'])
        print(f"✓ Configuration validated")
        return True

    def create_output_directory(self):
        """Create output directory if it doesn't exist."""
        output_dir = self.config['_out_dir']
        os.makedirs(output_dir, exist_ok=True)
        print(f"✓ Output directory: {output_dir}")

    def print_configuration_summary(self):
        """Print a summary of the configuration."""
        print("\n" + "="*60)
        print("IMGT2SEQ CONFIGURATION SUMMARY")
        print("="*60)
        print(f"IMGT input:         {self.config['_imgt']}")
        print(f"Genome build:       {self.config['_hg']}")
        print(f"Output directory:   {self.config['_out_dir']}")
        print(f"IMGT dir:           {self.config['_imgt_dir']}")
        print(f"No Indel:           {self.config['_no_Indel']}")
        print(f"MultiP:             {self.config['_MultiP']}")
        print(f"Save intermediates: {self.config['_f_save_intermediates']}")
        print(f"No prime:           {self.config['_no_prime']}")
        print(f"p_data:             {self.config['_p_data']}")
        print(f"Nfield output fmt:  {self.config['__Nfield_OUTPUT_FORMAT']}")
        print(f"HLA target:         {', '.join(self.config['_HLA_target'])}")
        print("="*60)

    def run_imgt2seq(self):
        """Run the IMGT2Seq function with loaded configuration."""
        try:
            result = IMGT2Seq.IMGT2Seq(
                _imgt=self.config['_imgt'],
                _hg=self.config['_hg'],
                _out_dir=self.config['_out_dir'],
                _imgt_dir=self.config['_imgt_dir'],
                _no_Indel=self.config['_no_Indel'],
                _MultiP=self.config['_MultiP'],
                _f_save_intermediates=self.config['_f_save_intermediates'],
                _no_prime=self.config['_no_prime'],
                _p_data=self.config['_p_data'],
                __Nfield_OUTPUT_FORMAT=self.config['__Nfield_OUTPUT_FORMAT'],
                _HLA_target=tuple(self.config['_HLA_target'])
            )
            print("IMGT2Seq completed successfully!")
            self.result = result
            return result
        except Exception as e:
            print(f"Error running IMGT2Seq: {e}")
            import traceback
            traceback.print_exc()
            return None

    def run(self):
        """Main execution method."""
        try:
            self.load_config()
            self.validate_config()
            self.create_output_directory()
            self.print_configuration_summary()
            result = self.run_imgt2seq()
            return result is not None
        except Exception as e:
            print(f"\n❌ Error: {e}")
            return False

def main():
    """
    Main function to run IMGT2Seq with configuration from YAML file
    """
    # Path to configuration file
    current_dir = Path(__file__).parent
    config_file = os.path.join(current_dir, "imgt2seq_run_config.yaml")
    
    print(f"Starting IMGT2Seq with configuration from {config_file}")
    
    # Load configuration
    config = IMGT2SeqRunner(config_file).load_config()
    
    # Create output directory if it doesn't exist
    output_dir = config["_out_dir"]
    os.makedirs(output_dir, exist_ok=True)
    print(f"Output directory: {output_dir}")
    
    # Run IMGT2Seq with configuration
    try:
        result = IMGT2Seq.IMGT2Seq(
            _imgt=config["_imgt"],
            _hg=config["_hg"],
            _out_dir=config["_out_dir"],
            _imgt_dir=config["_imgt_dir"],
            _no_Indel=config["_no_Indel"],
            _MultiP=config["_MultiP"],
            _f_save_intermediates=config["_f_save_intermediates"],
            _no_prime=config["_no_prime"],
            _p_data=config["_p_data"],
            __Nfield_OUTPUT_FORMAT=config["__Nfield_OUTPUT_FORMAT"],
            _HLA_target=tuple(config["_HLA_target"])  # Convert list to tuple
        )
        
        print("IMGT2Seq completed successfully!")
        return result
        
    except Exception as e:
        print(f"Error running IMGT2Seq: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    main() 