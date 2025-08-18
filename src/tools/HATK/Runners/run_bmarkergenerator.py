#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
run_bmarkergenerator.py
=======================
bMarkerGenerator execution script with YAML configuration support.

This script reads configuration from a YAML file and executes the bMarkerGenerator
function with the specified parameters.

bMarkerGenerator generates a marker panel using binary marker strategy for HLA region
polymorphism analysis. It creates 4 classes of markers:
1. HLA allele binary markers (ex. HLA_A*01:01)
2. Amino acid residue binary markers (ex. AA_A_9_30018537_exon2_F)
3. Intragenic(exonic/intronic) SNP binary markers (ex. SNPS_A_228_30018537_exon2_A)
4. Intergenic SNP variant markers (ex. rs9269186, rs41557221)

Usage:
    python src/tools/HATK/Runners/run_bmarkergenerator.py [config_file]
    
    If no config file is specified, it will look for 'bmarkergenerator_run_config.yaml'
    in the Runners directory.

Examples:
    # Full analysis with intergenic SNPs
    python src/tools/HATK/Runners/run_bmarkergenerator.py
    
    # HLA-only analysis
    python src/tools/HATK/Runners/run_bmarkergenerator.py hla_only_config.yaml
    
    # Custom configuration
    python src/tools/HATK/Runners/run_bmarkergenerator.py --config my_config.yaml --verbose

Author: HLAgent Development Team
Date: 2025
"""

import os
import sys
import time
import yaml
import argparse
import shutil
from pathlib import Path
from typing import Dict, Any, List, Tuple, Union

# Add project root to Python path
project_root = str(Path(__file__).parents[4])  # Go up 4 levels to reach project root
if project_root not in sys.path:
    sys.path.append(project_root)

from src.tools.HATK.bMarkerGenerator import bMarkerGenerator
from src.tools.HATK.NomenCleaner.src.CHPED import CHPED


class bMarkerGeneratorRunner:
    """
    bMarkerGenerator execution wrapper with YAML configuration support.
    
    This class provides a comprehensive interface for running bMarkerGenerator
    with YAML-based configuration, validation, and detailed reporting.
    """
    
    def __init__(self, config_f: str = "bmarkergenerator_run_config.yaml"):
        # Get the directory containing this script
        current_dir = Path(__file__).parent
        self.config_path = os.path.join(current_dir, config_f)
        self.config = {}
        self.start_time = None
        self.end_time = None
        self.stage_times = {}
        
    def load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            print(f"✓ Configuration loaded from: {self.config_path}")
            
            # Log configuration summary
            if self.config.get('_logging', {}).get('log_level', 'INFO') == 'DEBUG':
                print("DEBUG: Configuration loaded:")
                for key, value in self.config.items():
                    if not key.startswith('_'):
                        continue
                    print(f"  {key}: {value}")
                        
            return self.config
        except FileNotFoundError:
            raise FileNotFoundError(f"Configuration file not found: {self.config_path}")
        except yaml.YAMLError as e:
            raise ValueError(f"Error parsing YAML file: {e}")
    
    def validate_config(self) -> bool:
        """Validate the configuration parameters."""
        required_params = ['_chped', '_out', '_hg', '_dictionary_AA_seq', 
                          '_dictionary_AA_map', '_dictionary_SNPS_seq', '_dictionary_SNPS_map']
        
        for param in required_params:
            if param not in self.config:
                raise ValueError(f"Required parameter '{param}' not found in configuration")
        
        # Validate human genome build
        valid_hg = ['18', '19', '38']
        if self.config['_hg'] not in valid_hg:
            raise ValueError(f"Invalid human genome build: {self.config['_hg']}. Valid options: {valid_hg}")
        
        # Validate input files if enabled
        if self.config.get('_validation', {}).get('check_input_files', True):
            chped_path = self.config['_chped']
            
            if not os.path.exists(chped_path):
                raise FileNotFoundError(f"CHPED file not found: {chped_path}")
            
            print(f"✓ Input files validated")
            print(f"  - CHPED: {chped_path}")
        
        # Validate dictionary files if enabled
        if self.config.get('_validation', {}).get('check_dictionary_files', True):
            dict_files = [
                ('AA_seq', self.config['_dictionary_AA_seq']),
                ('AA_map', self.config['_dictionary_AA_map']),
                ('SNPS_seq', self.config['_dictionary_SNPS_seq']),
                ('SNPS_map', self.config['_dictionary_SNPS_map'])
            ]
            
            for dict_name, dict_path in dict_files:
                if not os.path.exists(dict_path):
                    raise FileNotFoundError(f"Dictionary file ({dict_name}) not found: {dict_path}")
            
            print(f"✓ Dictionary files validated")
            for dict_name, dict_path in dict_files:
                print(f"  - {dict_name}: {dict_path}")
        
        # Validate variants file if specified
        variants_path = self.config.get('_variants')
        if variants_path and variants_path != "null":
            if not os.path.exists(f"{variants_path}.bed"):
                print(f"⚠️  Warning: Variants file not found: {variants_path}.bed")
                print(f"   Will proceed with HLA-only analysis")
                self.config['_variants'] = None
            else:
                print(f"✓ Variants file validated: {variants_path}")
        
        # Check PLINK availability if enabled
        if self.config.get('_validation', {}).get('check_plink_availability', True):
            plink_path = self.config.get('_plink', 'plink')
            if shutil.which(plink_path) is None:
                raise FileNotFoundError(f"PLINK executable not found: {plink_path}")
            print(f"✓ PLINK executable validated: {plink_path}")
        
        # Validate HLA compatibility if enabled
        if self.config.get('_validation', {}).get('check_hla_compatibility', True):
            try:
                chped_obj = CHPED(self.config['_chped'])
                chped_hla_genes = set(chped_obj.HLA_avail)
                config_hla_genes = set(self.config.get('_HLA_target', []))
                
                missing_genes = config_hla_genes - chped_hla_genes
                if missing_genes:
                    raise ValueError(f"❌ HLA gene compatibility error! CHPED file missing HLA genes: {missing_genes}\n"
                                   f"   CHPED contains: {sorted(chped_hla_genes)}\n"
                                   f"   Config requests: {sorted(config_hla_genes)}")
                
                print(f"✓ HLA gene compatibility verified")
                print(f"  - CHPED genes: {sorted(chped_hla_genes)}")
                print(f"  - Config genes: {sorted(config_hla_genes)}")
            except Exception as e:
                print(f"⚠️  Could not verify HLA gene compatibility: {e}")
        
        # Validate binary marker settings
        binary_settings = self.config.get('_binary_marker_settings', {})
        if not any([
            binary_settings.get('include_hla_alleles', True),
            binary_settings.get('include_aa_residues', True), 
            binary_settings.get('include_intragenic_snps', True),
            binary_settings.get('include_intergenic_snps', True)
        ]):
            raise ValueError("At least one marker type must be enabled in _binary_marker_settings")
        
        return True
    
    def create_output_directory(self, out_path: str):
        """Create output directory if it doesn't exist."""
        if self.config.get('_create_output_dir', True):
            out_dir = os.path.dirname(out_path)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
                print(f"✓ Created output directory: {out_dir}")
                
            # Create temp directory if specified
            temp_dir = self.config.get('_resources', {}).get('temp_dir', 'temp')
            if temp_dir and not os.path.exists(temp_dir):
                os.makedirs(temp_dir, exist_ok=True)
                print(f"✓ Created temporary directory: {temp_dir}")
    
    def print_configuration_summary(self):
        """Print a summary of the configuration."""
        print("\n" + "="*80)
        print("BMARKERGENERATOR CONFIGURATION SUMMARY")
        print("="*80)
        print(f"📁 Input CHPED file:       {self.config['_chped']}")
        print(f"📁 Output prefix:          {self.config['_out']}")
        print(f"🧬 Human genome build:     {self.config['_hg']}")
        
        print(f"\n📚 Dictionary Files:")
        print(f"   AA sequence:            {self.config['_dictionary_AA_seq']}")
        print(f"   AA map:                 {self.config['_dictionary_AA_map']}")
        print(f"   SNPS sequence:          {self.config['_dictionary_SNPS_seq']}")
        print(f"   SNPS map:               {self.config['_dictionary_SNPS_map']}")
        
        variants = self.config.get('_variants')
        print(f"🔗 Variants files:          {variants if variants else 'None (HLA-only analysis)'}")
        
        print(f"\n⚙️  Processing Options:")
        print(f"   Save intermediates:     {self.config.get('_f_save_intermediates', False)}")
        print(f"   PLINK path:             {self.config.get('_plink', 'plink')}")
        
        print(f"\n🧬 HLA Target Genes:       {', '.join(self.config.get('_HLA_target', []))}")
        
        # Binary marker settings
        binary_settings = self.config.get('_binary_marker_settings', {})
        print(f"\n🎯 Binary Marker Settings:")
        print(f"   HLA alleles:            {binary_settings.get('include_hla_alleles', True)}")
        print(f"   AA residues:            {binary_settings.get('include_aa_residues', True)}")
        print(f"   Intragenic SNPs:        {binary_settings.get('include_intragenic_snps', True)}")
        print(f"   Intergenic SNPs:        {binary_settings.get('include_intergenic_snps', True)}")
        
        # Processing stages
        stages = self.config.get('_stages', {})
        enabled_stages = [k.replace('_', ' ').title() for k, v in stages.items() if v]
        print(f"\n🔄 Enabled Stages:         {', '.join(enabled_stages)}")
        
        # QC parameters
        qc = self.config.get('_qc_parameters', {})
        print(f"\n🎛️  QC Parameters:")
        print(f"   MIND threshold:         {qc.get('mind', 0.3)}")
        print(f"   GENO threshold:         {qc.get('geno', 0.5)}")
        print(f"   MAF threshold:          {qc.get('maf_threshold', 0.0001)}")
        print(f"   HWE threshold:          {qc.get('hwe_threshold', 0.000001)}")
        
        print("="*80)
    
    def _start_stage_timer(self, stage_name: str):
        """Start timing for a processing stage."""
        if self.config.get('_performance', {}).get('show_stage_timing', True):
            self.stage_times[stage_name] = time.time()
    
    def _end_stage_timer(self, stage_name: str):
        """End timing for a processing stage and print result."""
        if stage_name in self.stage_times and self.config.get('_performance', {}).get('show_stage_timing', True):
            duration = time.time() - self.stage_times[stage_name]
            print(f"   ⏱️  {stage_name} completed in {duration:.2f} seconds")
            del self.stage_times[stage_name]
    
    def _generate_output_prefix(self):
        """Generate output prefix based on input CHPED file name."""
        chped_path = self.config['_chped']
        out_dir = self.config['_out']
        
        # Get the base name of the CHPED file without extension
        chped_basename = os.path.splitext(os.path.basename(chped_path))[0]
        
        # Create output prefix with 'bMGen_' prefix and ensure 'hg' is added to genome build
        hg = self.config['_hg']
        if not hg.startswith('hg'):
            hg = f"hg{hg}"
        output_prefix = os.path.join(out_dir, f"bMGen_{chped_basename}.{hg}")
        
        print(f"✓ Generated output prefix: {output_prefix}")
        return output_prefix

    def run_bmarkergenerator(self) -> str:
        """Execute the bMarkerGenerator function."""
        
        # Prepare CHPED object
        self._start_stage_timer("CHPED Loading")
        chped_path = self.config['_chped']
        chped_obj = CHPED(chped_path)
        self._end_stage_timer("CHPED Loading")
        
        # Generate output prefix
        out_path = self._generate_output_prefix()
        
        # Create output directory
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        # Prepare other parameters
        hg = self.config['_hg']
        dict_aa_seq = self.config['_dictionary_AA_seq']
        dict_aa_map = self.config['_dictionary_AA_map']
        dict_snps_seq = self.config['_dictionary_SNPS_seq']
        dict_snps_map = self.config['_dictionary_SNPS_map']
        variants = self.config.get('_variants')
        f_save_intermediates = self.config.get('_f_save_intermediates', False)
        plink = self.config.get('_plink', 'plink')
        
        # Show progress if enabled
        if self.config.get('_performance', {}).get('show_progress', True):
            print(f"\n🔄 Starting bMarkerGenerator processing...")
            print(f"📊 Processing HLA genes: {', '.join(chped_obj.HLA_avail)}")
            print(f"📊 Field format: {chped_obj.field_format}")
            print(f"📊 Binary marker strategy: Multi-allelic positions → Binary markers (Presence/Absence)")
            print(f"📊 Output prefix: {out_path}")
            
            # Show marker types that will be generated
            binary_settings = self.config.get('_binary_marker_settings', {})
            marker_types = []
            if binary_settings.get('include_hla_alleles', True):
                marker_types.append("HLA alleles")
            if binary_settings.get('include_aa_residues', True):
                marker_types.append("AA residues")  
            if binary_settings.get('include_intragenic_snps', True):
                marker_types.append("Intragenic SNPs")
            if binary_settings.get('include_intergenic_snps', True) and variants:
                marker_types.append("Intergenic SNPs")
            
            print(f"🎯 Marker types to generate: {', '.join(marker_types)}")
            print(f"📊 Save intermediates: {f_save_intermediates}")
        
        # Measure execution time if enabled
        if self.config.get('_performance', {}).get('measure_time', True):
            self.start_time = time.time()
        
        try:
            # Execute bMarkerGenerator
            self._start_stage_timer("bMarkerGenerator Execution")
            result = bMarkerGenerator.bMarkerGenerator(
                _CHPED=chped_obj,
                _out=out_path,
                _hg=hg,
                _dictionary_AA_seq=dict_aa_seq,
                _dictionary_AA_map=dict_aa_map,
                _dictionary_SNPS_seq=dict_snps_seq,
                _dictionary_SNPS_map=dict_snps_map,
                _variants=variants,
                _f_save_intermediates=f_save_intermediates,
                _plink=plink,
                _config=self.config  # Pass the entire configuration
            )
            self._end_stage_timer("bMarkerGenerator Execution")
            
            if self.config.get('_performance', {}).get('measure_time', True):
                self.end_time = time.time()
            
            return result
            
        except Exception as e:
            if self.config.get('_performance', {}).get('measure_time', True):
                self.end_time = time.time()
            raise e
    
    def analyze_output_files(self, out_path: str) -> Dict[str, Any]:
        """Analyze generated output files and return statistics."""
        output_analysis = {
            'files_generated': [],
            'total_size': 0,
            'marker_counts': {},
            'file_details': {}
        }
        
        # Standard output files to check
        standard_files = [
            ('.bed', 'PLINK binary genotype file'),
            ('.bim', 'PLINK variant information file'),
            ('.fam', 'PLINK sample information file'),
            ('.FRQ.frq', 'Allele frequency file'),
            ('.log', 'PLINK log file'),
            ('.nosex', 'PLINK no-sex file')
        ]
        
        for ext, description in standard_files:
            file_path = f"{out_path}{ext}"
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                output_analysis['files_generated'].append(os.path.basename(file_path))
                output_analysis['total_size'] += file_size
                output_analysis['file_details'][ext] = {
                    'path': file_path,
                    'size': file_size,
                    'description': description
                }
                
                # Analyze .bim file for marker counts
                if ext == '.bim':
                    try:
                        with open(file_path, 'r') as f:
                            lines = f.readlines()
                            total_markers = len(lines)
                            output_analysis['marker_counts']['total'] = total_markers
                            
                            # Count different marker types
                            hla_count = sum(1 for line in lines if 'HLA_' in line)
                            aa_count = sum(1 for line in lines if 'AA_' in line)
                            snps_count = sum(1 for line in lines if 'SNPS_' in line)
                            other_count = total_markers - hla_count - aa_count - snps_count
                            
                            output_analysis['marker_counts'].update({
                                'hla_alleles': hla_count,
                                'aa_residues': aa_count,
                                'intragenic_snps': snps_count,
                                'intergenic_snps': other_count
                            })
                    except Exception as e:
                        print(f"⚠️  Could not analyze .bim file: {e}")
        
        return output_analysis
    
    def print_results_summary(self, result, output_analysis: Dict[str, Any]):
        """Print a detailed summary of the results."""
        print("\n" + "="*80)
        print("BMARKERGENERATOR RESULTS SUMMARY")
        print("="*80)
        
        if result:
            print(f"✅ bMarkerGenerator completed successfully!")
            print(f"📁 Result object: {type(result).__name__}")
            
            # Key mapping for pretty output
            key_map = {
                'file_prefix': 'File prefix',
                'bed': 'BED',
                'bim': 'BIM',
                'fam': 'FAM',
                'N_samples': 'Samples',
                'l_HLA_target': 'HLA target',
                'FRQ': 'Allele frequency file',
                'm_total': 'Total',
                'm_SNP': 'SNP',
                'm_HLA': 'HLA',
                'm_AA': 'AA',
                'm_SNPS': 'SNPS',
                'm_INS': 'INS',
                'f_hasSexInfo': 'Has sex info',
                'f_hasPheInfo': 'Has phenotype info',
                'f_save_intermediates': 'Save intermediates',
            }
            print(f"📊 Result attributes:")
            for attr, value in result.__dict__.items():
                # Pretty print l_HLA_target
                if attr == 'l_HLA_target':
                    # Remove np.str_ and convert to plain string
                    value = [str(x).replace("np.str_('", "").replace("')", "") for x in value]
                    print(f"   {key_map.get(attr, attr)}: {value}")
                # Remove m_ and f_ prefix for other keys
                elif attr.startswith('m_') and attr in key_map:
                    print(f"   {key_map[attr]}: {value}")
                elif attr.startswith('f_') and attr in key_map:
                    print(f"   {key_map[attr]}: {value}")
                else:
                    # Use mapped key if available, else original
                    print(f"   {key_map.get(attr, attr)}: {value}")
            
            # Show output file analysis
            if output_analysis['files_generated']:
                print(f"\n📄 Output Files Generated: {len(output_analysis['files_generated'])}")
                for file_name in output_analysis['files_generated']:
                    ext = '.' + file_name.split('.', 1)[1] if '.' in file_name else file_name
                    if ext in output_analysis['file_details']:
                        details = output_analysis['file_details'][ext]
                        size_mb = details['size'] / (1024 * 1024)
                        print(f"   📄 {file_name}: {size_mb:.2f} MB - {details['description']}")
                
                total_size_mb = output_analysis['total_size'] / (1024 * 1024)
                print(f"   📊 Total size: {total_size_mb:.2f} MB")
            
            # Show marker statistics
            if output_analysis['marker_counts']:
                print(f"\n🎯 Binary Marker Statistics:")
                marker_counts = output_analysis['marker_counts']
                if 'total' in marker_counts:
                    print(f"   Total markers: {marker_counts['total']:,}")
                if 'hla_alleles' in marker_counts:
                    print(f"   HLA allele markers: {marker_counts['hla_alleles']:,}")
                if 'aa_residues' in marker_counts:
                    print(f"   AA residue markers: {marker_counts['aa_residues']:,}")
                if 'intragenic_snps' in marker_counts:
                    print(f"   Intragenic SNP markers: {marker_counts['intragenic_snps']:,}")
                if 'intergenic_snps' in marker_counts:
                    print(f"   Intergenic SNP markers: {marker_counts['intergenic_snps']:,}")
            
            # Show processing summary
            variants = self.config.get('_variants')
            if variants:
                print(f"\n📊 Analysis Type: Full analysis (HLA + Intergenic SNPs)")
                print(f"   Input variants: {variants}")
            else:
                print(f"\n📊 Analysis Type: HLA-only analysis")
            
            print(f"   HLA genes processed: {', '.join(self.config.get('_HLA_target', []))}")
            print(f"   Binary marker strategy: ✓ Applied")
                
        else:
            print("❌ bMarkerGenerator returned no result")
        
        # Show execution time
        if self.start_time and self.end_time:
            execution_time = self.end_time - self.start_time
            print(f"\n⏱️  Total execution time: {execution_time:.2f} seconds")
            
            # Show stage timings if available
            if hasattr(self, 'stage_times') and self.stage_times:
                print(f"   Stage timings:")
                for stage, start_time in self.stage_times.items():
                    duration = time.time() - start_time
                    print(f"     {stage}: {duration:.2f}s")
        
        print("="*80)
    
    def save_summary(self, result, output_analysis: Dict[str, Any]):
        """Save processing summary to file."""
        if self.config.get('_save_summary', True):
            # Use the actual output prefix from result object
            if result and hasattr(result, 'file_prefix'):
                out_path = result.file_prefix
            else:
                # Fallback to config out path if result is not available
                out_path = self.config['_out']
            
            summary_file = f"{out_path}_summary.txt"
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(summary_file), exist_ok=True)
            
            with open(summary_file, 'w') as f:
                f.write("bMarkerGenerator Processing Summary\n")
                f.write("="*60 + "\n\n")
                f.write(f"Configuration file: {self.config_path}\n")
                f.write(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
                
                f.write("Input Configuration:\n")
                f.write(f"  CHPED file: {self.config['_chped']}\n")
                f.write(f"  Output prefix: {out_path}\n")  # Use actual output prefix
                f.write(f"  Human genome build: {self.config['_hg']}\n")
                f.write(f"  Variants file: {self.config.get('_variants', 'None')}\n")
                f.write(f"  Save intermediates: {self.config.get('_f_save_intermediates', False)}\n")
                f.write(f"  HLA targets: {', '.join(self.config.get('_HLA_target', []))}\n\n")
                
                # Binary marker settings
                binary_settings = self.config.get('_binary_marker_settings', {})
                f.write("Binary Marker Settings:\n")
                f.write(f"  HLA alleles: {binary_settings.get('include_hla_alleles', True)}\n")
                f.write(f"  AA residues: {binary_settings.get('include_aa_residues', True)}\n")
                f.write(f"  Intragenic SNPs: {binary_settings.get('include_intragenic_snps', True)}\n")
                f.write(f"  Intergenic SNPs: {binary_settings.get('include_intergenic_snps', True)}\n\n")
                
                if result:
                    f.write("Processing Results:\n")
                    f.write("  Status: SUCCESS\n")
                    f.write(f"  Result type: {type(result).__name__}\n")
                    
                    # Output file information
                    if output_analysis['files_generated']:
                        f.write(f"  Files generated: {len(output_analysis['files_generated'])}\n")
                        for file_name in output_analysis['files_generated']:
                            f.write(f"    - {file_name}\n")
                        
                        total_size_mb = output_analysis['total_size'] / (1024 * 1024)
                        f.write(f"  Total output size: {total_size_mb:.2f} MB\n")
                    
                    # Marker statistics
                    if output_analysis['marker_counts']:
                        f.write("\n  Marker Statistics:\n")
                        marker_counts = output_analysis['marker_counts']
                        for marker_type, count in marker_counts.items():
                            f.write(f"    {marker_type}: {count:,}\n")
                else:
                    f.write("Processing Results:\n")
                    f.write("  Status: FAILED\n")
                
                if self.start_time and self.end_time:
                    f.write(f"\nExecution time: {self.end_time - self.start_time:.2f} seconds\n")
            
            print(f"📄 Summary saved to: {summary_file}")
    
    def cleanup_temp_files(self):
        """Clean up temporary files if enabled."""
        if self.config.get('_resources', {}).get('cleanup_temp', True):
            temp_dir = self.config.get('_resources', {}).get('temp_dir', 'temp')
            if os.path.exists(temp_dir) and os.path.isdir(temp_dir):
                try:
                    shutil.rmtree(temp_dir)
                    print(f"🧹 Cleaned up temporary directory: {temp_dir}")
                except Exception as e:
                    print(f"⚠️  Could not clean up temporary directory: {e}")
    
    def run(self):
        """Main execution method."""
        try:
            # Load and validate configuration
            self.load_config()
            self.validate_config()
            
            # Print configuration summary
            if self.config.get('_verbose', True):
                self.print_configuration_summary()
            
            # Run bMarkerGenerator
            result = self.run_bmarkergenerator()
            
            # Analyze output files
            output_analysis = self.analyze_output_files(self.config['_out'])
            
            # Print results summary
            if self.config.get('_verbose', True):
                self.print_results_summary(result, output_analysis)
            
            # Save summary
            self.save_summary(result, output_analysis)
            
            # Cleanup temporary files
            self.cleanup_temp_files()
            
            print(f"\n🎉 bMarkerGenerator completed successfully!")
            print(f"📁 Output files available at: {self.config['_out']}.*")
            return True
            
        except Exception as e:
            print(f"\n❌ Error: {e}")
            if self.config.get('_verbose', True):
                import traceback
                traceback.print_exc()
            return False


def main():
    """Main function with command-line argument parsing."""
    parser = argparse.ArgumentParser(
        description="Run bMarkerGenerator with YAML configuration",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
bMarkerGenerator generates binary markers for HLA region polymorphism analysis.

Four classes of markers are generated:
  1. HLA allele binary markers (ex. HLA_A*01:01)
  2. Amino acid residue binary markers (ex. AA_A_9_30018537_exon2_F)  
  3. Intragenic SNP binary markers (ex. SNPS_A_228_30018537_exon2_A)
  4. Intergenic SNP variant markers (ex. rs9269186, rs41557221)

Examples:
    # Full analysis with intergenic SNPs (equivalent to HATK.py --bmarkergenerator with --variants)
    python run_bmarkergenerator.py
    
    # HLA-only analysis (equivalent to HATK.py --bmarkergenerator without --variants)
    python run_bmarkergenerator.py hla_only_config.yaml
    
    # Custom configuration with verbose output
    python run_bmarkergenerator.py --config my_config.yaml --verbose
        """
    )
    
    parser.add_argument(
        'config_file', 
        nargs='?',
        default='bmarkergenerator_run_config.yaml',
        help='Path to YAML configuration file (default: bmarkergenerator_run_config.yaml)'
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
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Validate configuration and show summary without running'
    )
    
    args = parser.parse_args()
    
    # Determine config file path
    config_path = args.config_file_alt if args.config_file_alt else args.config_file
    
    # Create bMarkerGenerator runner
    runner = bMarkerGeneratorRunner(config_path)
    
    # Override verbose setting if specified
    if args.verbose:
        runner.config = runner.config or {}
        runner.config['_verbose'] = True
    
    # Handle dry run
    if args.dry_run:
        try:
            runner.load_config()
            runner.validate_config()
            if runner.config.get('_verbose', True):
                runner.print_configuration_summary()
            print("\n✅ Configuration validation successful! Ready to run.")
            sys.exit(0)
        except Exception as e:
            print(f"\n❌ Configuration validation failed: {e}")
            sys.exit(1)
    
    # Run bMarkerGenerator
    success = runner.run()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
