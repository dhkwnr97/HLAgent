#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SmartRegression.py

An intelligent regression module for HLAgent that automatically determines
whether to use linear or logistic regression based on the phenotype data.

This module integrates with HATK (HLA Analysis Toolkit) and uses PLINK
for association analysis.

Author: HLAgent Development Team
Date: 2025
"""

import os
import sys
import re
import pandas as pd
import numpy as np
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union
from pathlib import Path

# Module information
__version__ = "1.0.0"
__author__ = "HLAgent Development Team"

# Standard output prefixes
std_MAIN = "\n[SmartRegression]: "
std_ERROR = "\n[SmartRegression::ERROR]: "
std_WARNING = "\n[SmartRegression::WARNING]: "
std_INFO = "\n[SmartRegression::INFO]: "

class SmartRegression:
    """
    Smart regression analysis for HLA fine-mapping.
    Automatically determines the appropriate regression type based on phenotype data.
    """
    
    def __init__(self, bfile_prefix: str, output_prefix: str, 
                 pheno_file: Optional[str] = None, pheno_name: Optional[str] = None,
                 covar_file: Optional[str] = None, covar_names: Optional[Union[str, List[str]]] = None,
                 condition_list: Optional[str] = None,
                 chr: int = 6, from_mb: float = 29, to_mb: float = 34,
                 ci: float = 0.95, plink_path: str = "plink",
                 verbose: bool = True):
        """
        Initialize SmartRegression.
        
        Args:
            bfile_prefix: Prefix for PLINK binary files (.bed, .bim, .fam)
            output_prefix: Prefix for output files
            pheno_file: Phenotype file (optional, can use .fam)
            pheno_name: Column name in phenotype file
            covar_file: Covariate file
            covar_names: Covariate column names
            condition_list: File with variant IDs for conditional analysis
            chr: Chromosome (default: 6 for HLA region)
            from_mb: Start position in Mb (default: 29)
            to_mb: End position in Mb (default: 34)
            ci: Confidence interval (default: 0.95)
            plink_path: Path to PLINK executable
            verbose: Enable verbose output
        """
        self.bfile_prefix = bfile_prefix
        self.output_prefix = output_prefix
        self.pheno_file = pheno_file
        self.pheno_name = pheno_name
        self.covar_file = covar_file
        self.covar_names = covar_names if isinstance(covar_names, list) else [covar_names] if covar_names else None
        self.condition_list = condition_list
        self.chr = chr
        self.from_mb = from_mb
        self.to_mb = to_mb
        self.ci = ci
        self.plink_path = plink_path
        self.verbose = verbose
        
        # Analysis results
        self.phenotype_type = None
        self.regression_type = None
        self.assoc_result = None
        self.summary_stats = None
        
        # Verify input files exist
        self._verify_input_files()
        
        # Log initialization
        if self.verbose:
            print(f"{std_INFO}SmartRegression initialized")
            print(f"{std_INFO}Input files: {self.bfile_prefix}.*")
            print(f"{std_INFO}Output prefix: {self.output_prefix}")
    
    def _verify_input_files(self):
        """Verify that all required input files exist."""
        required_extensions = ['.bed', '.bim', '.fam']
        for ext in required_extensions:
            file_path = self.bfile_prefix + ext
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"{std_ERROR}Required file not found: {file_path}")
        
        # Check optional files
        if self.pheno_file and not os.path.exists(self.pheno_file):
            raise FileNotFoundError(f"{std_ERROR}Phenotype file not found: {self.pheno_file}")
        
        if self.covar_file and not os.path.exists(self.covar_file):
            raise FileNotFoundError(f"{std_ERROR}Covariate file not found: {self.covar_file}")
        
        if self.condition_list and not os.path.exists(self.condition_list):
            raise FileNotFoundError(f"{std_ERROR}Condition list file not found: {self.condition_list}")
    
    def analyze_phenotype(self) -> str:
        """
        Analyze phenotype data to determine if it's binary or continuous.
        
        Returns:
            str: 'Binary' or 'Continuous'
        """
        if self.verbose:
            print(f"{std_INFO}Analyzing phenotype data...")
        
        # Load phenotype data
        if self.pheno_file:
            # Load from external phenotype file
            pheno_df = pd.read_csv(self.pheno_file, sep=r'\s+', header=0)
            
            if self.pheno_name:
                if self.pheno_name not in pheno_df.columns:
                    raise ValueError(f"{std_ERROR}Phenotype column '{self.pheno_name}' not found in phenotype file")
                pheno_values = pheno_df[self.pheno_name].dropna()
            else:
                # Use the last column if no specific name given
                pheno_values = pheno_df.iloc[:, -1].dropna()
        else:
            # Load from .fam file (6th column)
            fam_df = pd.read_csv(self.bfile_prefix + '.fam', sep=r'\s+', header=None)
            pheno_values = fam_df.iloc[:, 5]
            
            # Remove missing values (-9 in PLINK)
            pheno_values = pheno_values[pheno_values != -9]
            
            if len(pheno_values) == 0:
                raise ValueError(f"{std_ERROR}No valid phenotype values found in .fam file")
        
        # Determine phenotype type
        unique_values = pheno_values.unique()
        n_unique = len(unique_values)
        
        # Check if binary
        if n_unique == 2:
            # Check common binary encodings
            if set(unique_values) in [{0, 1}, {1, 2}, {-1, 1}]:
                self.phenotype_type = "Binary"
                if self.verbose:
                    print(f"{std_INFO}Detected binary phenotype with values: {sorted(unique_values)}")
            else:
                # Two unique values but not standard encoding
                self.phenotype_type = "Binary"
                if self.verbose:
                    print(f"{std_WARNING}Detected binary phenotype with non-standard values: {sorted(unique_values)}")
                    print(f"{std_WARNING}Consider recoding to 0/1 or 1/2 for PLINK compatibility")
        
        elif n_unique < 2:
            raise ValueError(f"{std_ERROR}Phenotype has less than 2 unique values. Cannot perform regression.")
        
        elif n_unique <= 10:
            # Likely ordinal or categorical, but we'll treat as continuous
            # unless it's clearly binary
            if self.verbose:
                print(f"{std_WARNING}Phenotype has {n_unique} unique values. Treating as continuous.")
                print(f"{std_WARNING}If this is categorical, consider recoding or using appropriate methods.")
            self.phenotype_type = "Continuous"
        else:
            # Many unique values, likely continuous
            self.phenotype_type = "Continuous"
            if self.verbose:
                print(f"{std_INFO}Detected continuous phenotype with {n_unique} unique values")
                print(f"{std_INFO}Value range: [{pheno_values.min():.3f}, {pheno_values.max():.3f}]")
        
        # Set regression type based on phenotype
        self.regression_type = "logistic" if self.phenotype_type == "Binary" else "linear"
        
        if self.verbose:
            print(f"{std_INFO}Will perform {self.regression_type} regression")
        
        return self.phenotype_type
    
    def run_regression(self) -> str:
        """
        Run the appropriate regression analysis using PLINK.
        
        Returns:
            str: Path to the association results file
        """
        if self.phenotype_type is None:
            self.analyze_phenotype()
        
        if self.verbose:
            print(f"{std_INFO}Running {self.regression_type} regression...")
        
        # Build PLINK command
        cmd = [self.plink_path]
        
        # Add regression type
        if self.regression_type == "logistic":
            cmd.append("--logistic")
        else:
            cmd.append("--linear")
        
        # Add hide-covar flag
        cmd.append("hide-covar")
        
        # Add input files
        cmd.extend(["--bfile", self.bfile_prefix])
        
        # Add phenotype
        if self.pheno_file:
            cmd.extend(["--pheno", self.pheno_file])
            if self.pheno_name:
                cmd.extend(["--pheno-name", self.pheno_name])
        
        # Add covariates
        if self.covar_file:
            cmd.extend(["--covar", self.covar_file])
            if self.covar_names:
                cmd.extend(["--covar-name", ",".join(self.covar_names)])
        
        # Add conditional analysis
        if self.condition_list:
            cmd.extend(["--condition-list", self.condition_list])
        
        # Add region restriction (HLA region)
        cmd.extend(["--chr", str(self.chr)])
        cmd.extend(["--from-mb", str(self.from_mb)])
        cmd.extend(["--to-mb", str(self.to_mb)])
        
        # Add confidence interval
        cmd.extend(["--ci", str(self.ci)])
        
        # Add other flags
        cmd.append("--allow-no-sex")
        cmd.append("--keep-allele-order")
        
        # Set output
        cmd.extend(["--out", self.output_prefix])
        
        # Log command
        if self.verbose:
            print(f"{std_INFO}PLINK command: {' '.join(cmd)}")
        
        # Execute PLINK
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            if self.verbose:
                print(f"{std_INFO}PLINK execution completed successfully")
            
            # Save log
            log_file = self.output_prefix + ".log"
            with open(log_file, 'w') as f:
                f.write(result.stdout)
                if result.stderr:
                    f.write("\n\nSTDERR:\n")
                    f.write(result.stderr)
            
        except subprocess.CalledProcessError as e:
            print(f"{std_ERROR}PLINK execution failed!")
            print(f"{std_ERROR}Error: {e}")
            if e.stderr:
                print(f"{std_ERROR}STDERR: {e.stderr}")
            raise
        
        # Determine output file name
        if self.regression_type == "logistic":
            self.assoc_result = self.output_prefix + ".assoc.logistic"
        else:
            self.assoc_result = self.output_prefix + ".assoc.linear"
        
        # Verify output exists
        if not os.path.exists(self.assoc_result):
            raise FileNotFoundError(f"{std_ERROR}Expected output file not found: {self.assoc_result}")
        
        if self.verbose:
            print(f"{std_INFO}Association results saved to: {self.assoc_result}")
        
        return self.assoc_result
    
    def parse_results(self) -> pd.DataFrame:
        """
        Parse the association results and create summary statistics.
        
        Returns:
            pd.DataFrame: Parsed association results
        """
        if not self.assoc_result or not os.path.exists(self.assoc_result):
            raise ValueError(f"{std_ERROR}No association results to parse. Run regression first.")
        
        if self.verbose:
            print(f"{std_INFO}Parsing association results...")
        
        # Read results
        results_df = pd.read_csv(self.assoc_result, sep=r'\s+')
        
        # Add -log10(p) for visualization
        results_df['NEGLOG10P'] = -np.log10(results_df['P'])
        
        # Sort by p-value
        results_df = results_df.sort_values('P')
        
        # Store parsed results
        self.summary_stats = results_df
        
        return results_df
    
    def generate_summary(self, top_n: int = 20) -> Dict:
        """
        Generate a summary of the regression results.
        
        Args:
            top_n: Number of top associations to include
        
        Returns:
            dict: Summary statistics and top associations
        """
        if self.summary_stats is None:
            self.parse_results()
        
        summary = {
            'regression_type': self.regression_type,
            'phenotype_type': self.phenotype_type,
            'total_variants': len(self.summary_stats),
            'significant_variants': len(self.summary_stats[self.summary_stats['P'] < 0.05]),
            'highly_significant_variants': len(self.summary_stats[self.summary_stats['P'] < 5e-8]),
            'top_associations': self.summary_stats.head(top_n).to_dict('records'),
            'analysis_date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        # Add HLA-specific information
        if 'SNP' in self.summary_stats.columns:
            hla_variants = self.summary_stats[self.summary_stats['SNP'].str.contains('HLA', na=False)]
            summary['hla_variants'] = len(hla_variants)
            
            # Calculate significant HLA variants
            if len(hla_variants) > 0:
                significant_hla = hla_variants[hla_variants['P'] < 5e-8]
                summary['significant_hla_variants'] = len(significant_hla)
            else:
                summary['significant_hla_variants'] = 0
            
            summary['top_hla_associations'] = hla_variants.head(10).to_dict('records')
        
        return summary
    
    def save_summary(self, filename: Optional[str] = None):
        """Save summary to JSON file."""
        if filename is None:
            filename = self.output_prefix + "_summary.json"
        
        summary = self.generate_summary()
        
        with open(filename, 'w') as f:
            json.dump(summary, f, indent=2)
        
        if self.verbose:
            print(f"{std_INFO}Summary saved to: {filename}")
        
        return filename
    
    def run_complete_analysis(self) -> Tuple[str, Dict]:
        """
        Run complete analysis pipeline.
        
        Returns:
            tuple: (association_file, summary_dict)
        """
        print(f"{std_INFO}Starting SmartRegression analysis...")
        
        # Step 1: Analyze phenotype
        self.analyze_phenotype()
        
        # Step 2: Run regression
        assoc_file = self.run_regression()
        
        # Step 3: Parse results
        self.parse_results()
        
        # Step 4: Generate and save summary
        summary = self.generate_summary()
        self.save_summary()
        
        print(f"{std_INFO}Analysis complete!")
        print(f"{std_INFO}Regression type: {self.regression_type}")
        print(f"{std_INFO}Total variants tested: {summary['total_variants']}")
        print(f"{std_INFO}Significant variants (P < 0.05): {summary['significant_variants']}")
        print(f"{std_INFO}Highly significant variants (P < 5e-8): {summary['highly_significant_variants']}")
        
        return assoc_file, summary
    
    def filter_results_by_significance(self, p_threshold: float = 0.05) -> pd.DataFrame:
        """
        Filter results by significance threshold.
        
        Args:
            p_threshold: P-value threshold for significance
            
        Returns:
            pd.DataFrame: Filtered significant associations
        """
        if self.summary_stats is None:
            self.parse_results()
        
        return self.summary_stats[self.summary_stats['P'] < p_threshold].copy()
    
    def get_hla_specific_results(self) -> pd.DataFrame:
        """
        Extract HLA-specific variants from results.
        
        Returns:
            pd.DataFrame: HLA-specific associations
        """
        if self.summary_stats is None:
            self.parse_results()
        
        if 'SNP' in self.summary_stats.columns:
            hla_mask = self.summary_stats['SNP'].str.contains('HLA', na=False, case=False)
            return self.summary_stats[hla_mask].copy()
        else:
            return pd.DataFrame()
    
    def get_top_associations(self, n: int = 10, by_hla: bool = False) -> pd.DataFrame:
        """
        Get top N associations.
        
        Args:
            n: Number of top associations to return
            by_hla: If True, return top HLA-specific associations only
            
        Returns:
            pd.DataFrame: Top associations
        """
        if by_hla:
            results = self.get_hla_specific_results()
        else:
            if self.summary_stats is None:
                self.parse_results()
            results = self.summary_stats
        
        return results.head(n).copy()
    
    def create_manhattan_data(self) -> pd.DataFrame:
        """
        Prepare data for Manhattan plot visualization.
        
        Returns:
            pd.DataFrame: Data formatted for Manhattan plot
        """
        if self.summary_stats is None:
            self.parse_results()
        
        manhattan_data = self.summary_stats.copy()
        
        # Ensure required columns exist
        if 'CHR' not in manhattan_data.columns:
            manhattan_data['CHR'] = self.chr
        
        if 'BP' not in manhattan_data.columns and 'POS' in manhattan_data.columns:
            manhattan_data['BP'] = manhattan_data['POS']
        
        return manhattan_data[['CHR', 'BP', 'SNP', 'P', 'NEGLOG10P']].copy()
    
    def export_results(self, format: str = 'csv', filename: Optional[str] = None) -> str:
        """
        Export results in various formats.
        
        Args:
            format: Export format ('csv', 'tsv', 'excel')
            filename: Output filename (optional)
            
        Returns:
            str: Path to exported file
        """
        if self.summary_stats is None:
            self.parse_results()
        
        if filename is None:
            filename = f"{self.output_prefix}_results.{format}"
        
        if format.lower() == 'csv':
            self.summary_stats.to_csv(filename, index=False)
        elif format.lower() == 'tsv':
            self.summary_stats.to_csv(filename, sep='\t', index=False)
        elif format.lower() == 'excel':
            self.summary_stats.to_excel(filename, index=False)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        if self.verbose:
            print(f"{std_INFO}Results exported to: {filename}")
        
        return filename
    
    def remove_intermediate_files(self):
        """
        Remove intermediate files generated during analysis.
        """
        intermediate_files = [
            self.output_prefix + ".log",
            self.output_prefix + ".nosex"
        ]
        
        for file_path in intermediate_files:
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    if self.verbose:
                        print(f"{std_INFO}Removed intermediate file: {file_path}")
                except Exception as e:
                    if self.verbose:
                        print(f"{std_WARNING}Could not remove {file_path}: {e}")
    
    def validate_phenotype_distribution(self) -> Dict:
        """
        Validate and describe phenotype distribution.
        
        Returns:
            dict: Phenotype distribution statistics
        """
        # Load phenotype data (similar to analyze_phenotype but for validation)
        if self.pheno_file:
            pheno_df = pd.read_csv(self.pheno_file, sep=r'\s+', header=0)
            if self.pheno_name:
                pheno_values = pheno_df[self.pheno_name].dropna()
            else:
                pheno_values = pheno_df.iloc[:, -1].dropna()
        else:
            fam_df = pd.read_csv(self.bfile_prefix + '.fam', sep=r'\s+', header=None)
            pheno_values = fam_df.iloc[:, 5]
            pheno_values = pheno_values[pheno_values != -9]
        
        validation_stats = {
            'n_samples': len(pheno_values),
            'n_missing': pheno_values.isna().sum(),
            'unique_values': len(pheno_values.unique()),
            'min_value': pheno_values.min(),
            'max_value': pheno_values.max(),
            'mean': pheno_values.mean(),
            'std': pheno_values.std(),
            'value_counts': pheno_values.value_counts().to_dict()
        }
        
        return validation_stats