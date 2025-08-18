#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
StepCon_SmartRegression.py

Enhanced Stepwise Conditional Regression for HLAgent using PLINK
================================================================

This module implements stepwise conditional regression analysis using PLINK
for standard genomic file formats (.bed, .bim, .fam, .phe).

Core Features:
- Automatic phenotype type detection (binary vs continuous)
- Stepwise forward selection with conditional analysis
- PLINK integration for robust association testing
- Support for HLA region analysis
- Efficient iteration management

Based on PLINK documentation: https://zzz.bwh.harvard.edu/plink/tutorial.shtml

Author: HLAgent Development Team
Date: 2025
"""

import os
import sys
import subprocess
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union, Any
import warnings
import logging

# Module information
__version__ = "2.0.0"
__author__ = "HLAgent Development Team"

# Standard output prefixes
std_MAIN = "\n[StepwiseRegression]: "
std_ERROR = "\n[StepwiseRegression::ERROR]: "
std_WARNING = "\n[StepwiseRegression::WARNING]: "
std_INFO = "\n[StepwiseRegression::INFO]: "

class StepwiseConditionalRegression:
    """
    Stepwise conditional regression using PLINK for genomic analysis.
    
    This class implements stepwise forward selection with conditional analysis,
    automatically detecting phenotype type and choosing appropriate regression method.
    """
    
    def __init__(self, 
                 bfile_prefix: str,
                 output_prefix: str,
                 pheno_file: Optional[str] = None,
                 pheno_name: Optional[str] = None,
                 covar_file: Optional[str] = None,
                 covar_names: Optional[List[str]] = None,
                 plink_path: str = "plink",
                 significance_threshold: float = 0.05,
                 genome_wide_threshold: float = 5e-8,
                 max_iterations: int = 100,
                 chr_filter: Optional[int] = None,
                 from_bp: Optional[int] = None,
                 to_bp: Optional[int] = None,
                 from_mb: Optional[float] = None,
                 to_mb: Optional[float] = None,
                 hla_region: bool = True,
                 verbose: bool = True):
        """
        Initialize Stepwise Conditional Regression.
        
        Args:
            bfile_prefix: Prefix for PLINK binary files (.bed, .bim, .fam)
            output_prefix: Prefix for output files
            pheno_file: External phenotype file (.phe format)
            pheno_name: Column name in phenotype file
            covar_file: Covariate file
            covar_names: List of covariate column names
            plink_path: Path to PLINK executable
            significance_threshold: P-value threshold for stepwise selection
            genome_wide_threshold: Genome-wide significance threshold
            max_iterations: Maximum number of stepwise iterations
            chr_filter: Chromosome to analyze (default: None for all)
            from_bp: Start position in base pairs
            to_bp: End position in base pairs
            from_mb: Start position in megabases
            to_mb: End position in megabases
            hla_region: If True, focus on HLA region (chr6:29-34Mb)
            verbose: Enable verbose output
        """
        self.bfile_prefix = bfile_prefix
        self.output_prefix = output_prefix
        self.pheno_file = pheno_file
        self.pheno_name = pheno_name
        self.covar_file = covar_file
        self.covar_names = covar_names or []
        self.plink_path = plink_path
        self.significance_threshold = significance_threshold
        self.genome_wide_threshold = genome_wide_threshold
        self.max_iterations = max_iterations
        self.chr_filter = chr_filter
        self.from_bp = from_bp
        self.to_bp = to_bp
        self.from_mb = from_mb
        self.to_mb = to_mb
        self.hla_region = hla_region
        self.verbose = verbose
        
        # Set HLA region defaults if enabled
        if self.hla_region and not self.chr_filter:
            self.chr_filter = 6
            self.from_mb = self.from_mb or 29
            self.to_mb = self.to_mb or 34
        
        # Analysis state
        self.phenotype_type = None
        self.regression_type = None
        self.selected_snps = []
        self.iteration_results = []
        self.final_results = None
        
        # Setup logging
        logging.basicConfig(level=logging.INFO if verbose else logging.WARNING)
        self.logger = logging.getLogger(__name__)
        
        # Verify input files
        self._verify_input_files()
        
        if self.verbose:
            print(f"{std_INFO}Stepwise Conditional Regression initialized")
            print(f"{std_INFO}Input files: {self.bfile_prefix}.*")
            print(f"{std_INFO}Output prefix: {self.output_prefix}")
            if self.hla_region:
                print(f"{std_INFO}HLA region analysis: Chr{self.chr_filter}:{self.from_mb}-{self.to_mb}Mb")
    
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
        
        # Check PLINK availability
        try:
            result = subprocess.run([self.plink_path, '--version'], 
                                  capture_output=True, text=True, timeout=10)
            if self.verbose:
                print(f"{std_INFO}PLINK version: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
            raise RuntimeError(f"{std_ERROR}PLINK not found or not executable: {self.plink_path}")
    
    def analyze_phenotype(self) -> str:
        """
        Analyze phenotype data to determine if it's binary or continuous.
        
        Returns:
            str: 'binary' or 'continuous'
        """
        if self.verbose:
            print(f"{std_INFO}Analyzing phenotype data...")
        
        # Load phenotype data
        if self.pheno_file:
            # Load from external phenotype file
            # PLINK .phe format: FID IID PHENO1 [PHENO2 ...]
            try:
                pheno_df = pd.read_csv(self.pheno_file, sep=r'\s+', header=0)
            except:
                # Try without header
                pheno_df = pd.read_csv(self.pheno_file, sep=r'\s+', header=None)
                if len(pheno_df.columns) >= 3:
                    pheno_df.columns = ['FID', 'IID'] + [f'PHENO{i}' for i in range(1, len(pheno_df.columns)-1)]
            
            if self.pheno_name:
                if self.pheno_name not in pheno_df.columns:
                    raise ValueError(f"{std_ERROR}Phenotype column '{self.pheno_name}' not found in phenotype file")
                pheno_values = pheno_df[self.pheno_name].dropna()
            else:
                # Use the third column (first phenotype) if no specific name given
                if len(pheno_df.columns) >= 3:
                    pheno_values = pheno_df.iloc[:, 2].dropna()
                else:
                    raise ValueError(f"{std_ERROR}Phenotype file must have at least 3 columns (FID, IID, PHENO)")
        else:
            # Load from .fam file (6th column)
            # PLINK .fam format: FID IID PID MID SEX PHENO
            fam_df = pd.read_csv(self.bfile_prefix + '.fam', sep=r'\s+', header=None)
            if len(fam_df.columns) < 6:
                raise ValueError(f"{std_ERROR}.fam file must have 6 columns")
            
            pheno_values = fam_df.iloc[:, 5]  # 6th column (0-indexed)
            
            # Remove missing values (-9, 0, or NA in PLINK)
            pheno_values = pheno_values[~pheno_values.isin([-9, 0])]
            pheno_values = pheno_values.dropna()
            
            if len(pheno_values) == 0:
                raise ValueError(f"{std_ERROR}No valid phenotype values found in .fam file")
        
        # Determine phenotype type
        unique_values = pheno_values.unique()
        n_unique = len(unique_values)
        
        # Check if binary
        if n_unique == 2:
            # Check common binary encodings
            unique_set = set(unique_values)
            if unique_set in [{0, 1}, {1, 2}, {-1, 1}, {0.0, 1.0}, {1.0, 2.0}]:
                self.phenotype_type = "binary"
                if self.verbose:
                    print(f"{std_INFO}Detected binary phenotype with values: {sorted(unique_values)}")
            else:
                # Two unique values but not standard encoding
                self.phenotype_type = "binary"
                if self.verbose:
                    print(f"{std_WARNING}Detected binary phenotype with non-standard values: {sorted(unique_values)}")
                    print(f"{std_WARNING}Consider recoding to 1/2 for PLINK compatibility")
        
        elif n_unique < 2:
            raise ValueError(f"{std_ERROR}Phenotype has less than 2 unique values. Cannot perform regression.")
        
        elif n_unique <= 10:
            # Check if all values are integers and within reasonable range for categorical
            if all(isinstance(v, (int, np.integer)) or (isinstance(v, float) and v.is_integer()) 
                   for v in unique_values):
                if self.verbose:
                    print(f"{std_WARNING}Phenotype has {n_unique} unique integer values.")
                    print(f"{std_WARNING}Treating as continuous. If categorical, consider binary encoding.")
            self.phenotype_type = "continuous"
        else:
            # Many unique values, likely continuous
            self.phenotype_type = "continuous"
            if self.verbose:
                print(f"{std_INFO}Detected continuous phenotype with {n_unique} unique values")
                print(f"{std_INFO}Value range: [{pheno_values.min():.3f}, {pheno_values.max():.3f}]")
        
        # Set regression type based on phenotype
        self.regression_type = "logistic" if self.phenotype_type == "binary" else "linear"
        
        if self.verbose:
            print(f"{std_INFO}Will perform {self.regression_type} regression")
        
        return self.phenotype_type
    
    def _build_plink_command(self, iteration: int, condition_snps: List[str] = None) -> Tuple[List[str], str]:
        """
        Build PLINK command for association analysis.
        
        Args:
            iteration: Current iteration number
            condition_snps: List of SNPs to condition on
            
        Returns:
            Tuple[List[str], str]: PLINK command arguments and output name
        """
        cmd = [self.plink_path]
        
        # Input files
        cmd.extend(["--bfile", self.bfile_prefix])
        
        # Regression type
        if self.regression_type == "logistic":
            cmd.append("--logistic")
        else:
            cmd.append("--linear")
        
        # Hide covariate output for cleaner results
        cmd.append("hide-covar")
        
        # Phenotype
        if self.pheno_file:
            cmd.extend(["--pheno", self.pheno_file])
            if self.pheno_name:
                cmd.extend(["--pheno-name", self.pheno_name])
        
        # Covariates
        if self.covar_file:
            cmd.extend(["--covar", self.covar_file])
            if self.covar_names:
                cmd.extend(["--covar-name", ",".join(self.covar_names)])
        
        # Conditional analysis
        if condition_snps:
            condition_file = f"{self.output_prefix}_conditions_iter{iteration}.txt"
            with open(condition_file, 'w') as f:
                for snp in condition_snps:
                    f.write(f"{snp}\n")
            cmd.extend(["--condition-list", condition_file])
        
        # Genomic region filters
        if self.chr_filter:
            cmd.extend(["--chr", str(self.chr_filter)])
        
        if self.from_bp and self.to_bp:
            cmd.extend(["--from-bp", str(self.from_bp)])
            cmd.extend(["--to-bp", str(self.to_bp)])
        elif self.from_mb and self.to_mb:
            cmd.extend(["--from-mb", str(self.from_mb)])
            cmd.extend(["--to-mb", str(self.to_mb)])
        
        # Additional PLINK options
        cmd.append("--allow-no-sex")
        cmd.append("--keep-allele-order")
        
        # Output
        output_name = f"{self.output_prefix}_iter{iteration}"
        cmd.extend(["--out", output_name])
        
        return cmd, output_name
    
    def _run_plink_association(self, iteration: int, condition_snps: List[str] = None) -> str:
        """
        Run PLINK association analysis for one iteration.
        
        Args:
            iteration: Current iteration number
            condition_snps: List of SNPs to condition on
            
        Returns:
            str: Path to association results file
        """
        cmd, output_name = self._build_plink_command(iteration, condition_snps)
        
        if self.verbose:
            print(f"{std_INFO}Running PLINK iteration {iteration}...")
            print(f"{std_INFO}Command: {' '.join(cmd)}")
        
        # Execute PLINK
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True, timeout=300)
            
            # Save log
            log_file = f"{output_name}.log"
            if os.path.exists(log_file):
                with open(log_file, 'a') as f:
                    f.write(f"\n\n=== COMMAND ===\n{' '.join(cmd)}\n")
                    if result.stderr:
                        f.write(f"\n=== STDERR ===\n{result.stderr}\n")
            
        except subprocess.CalledProcessError as e:
            print(f"{std_ERROR}PLINK execution failed at iteration {iteration}!")
            print(f"{std_ERROR}Error: {e}")
            if e.stderr:
                print(f"{std_ERROR}STDERR: {e.stderr}")
            raise
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"{std_ERROR}PLINK execution timed out at iteration {iteration}")
        
        # Determine output file name
        if self.regression_type == "logistic":
            assoc_file = f"{output_name}.assoc.logistic"
        else:
            assoc_file = f"{output_name}.assoc.linear"
        
        # Verify output exists
        if not os.path.exists(assoc_file):
            raise FileNotFoundError(f"{std_ERROR}Expected output file not found: {assoc_file}")
        
        return assoc_file
    
    def _parse_association_results(self, assoc_file: str, excluded_snps: List[str] = None) -> pd.DataFrame:
        """
        Parse PLINK association results.
        
        Args:
            assoc_file: Path to association results file
            excluded_snps: SNPs to exclude from consideration
            
        Returns:
            pd.DataFrame: Parsed association results
        """
        excluded_snps = excluded_snps or []
        
        try:
            # Read association results
            df = pd.read_csv(assoc_file, sep=r'\s+')
            
            # Filter out excluded SNPs
            if excluded_snps:
                df = df[~df['SNP'].isin(excluded_snps)]
            
            # Remove rows with missing p-values
            df = df.dropna(subset=['P'])
            
            # Sort by p-value
            df = df.sort_values('P')
            
            # Add -log10(P) for convenience
            df['NEGLOG10P'] = -np.log10(df['P'])
            
            return df
            
        except Exception as e:
            raise RuntimeError(f"{std_ERROR}Failed to parse association results: {e}")
    
    def run_stepwise_analysis(self) -> Dict[str, Any]:
        """
        Run complete stepwise conditional regression analysis.
        
        Returns:
            Dict[str, Any]: Complete analysis results
        """
        print(f"{std_MAIN}Starting Stepwise Conditional Regression Analysis")
        print(f"{std_INFO}Significance threshold: {self.significance_threshold}")
        print(f"{std_INFO}Genome-wide threshold: {self.genome_wide_threshold}")
        print(f"{std_INFO}Maximum iterations: {self.max_iterations}")
        
        start_time = time.time()
        
        # Step 1: Analyze phenotype
        if self.phenotype_type is None:
            self.analyze_phenotype()
        
        # Step 2: Stepwise selection
        iteration = 0
        selected_snps = []
        
        while iteration < self.max_iterations:
            iteration += 1
            
            if self.verbose:
                print(f"\n{std_INFO}=== Iteration {iteration} ===")
                if selected_snps:
                    print(f"{std_INFO}Conditioning on: {', '.join(selected_snps)}")
            
            # Run PLINK association
            try:
                assoc_file = self._run_plink_association(iteration, selected_snps)
                
                # Parse results
                results_df = self._parse_association_results(assoc_file, selected_snps)
                
                if results_df.empty:
                    print(f"{std_WARNING}No variants available for testing at iteration {iteration}")
                    break
                
                # Get best candidate
                best_snp = results_df.iloc[0]
                best_p = best_snp['P']
                best_snp_id = best_snp['SNP']
                
                # Store iteration results
                iteration_info = {
                    'iteration': iteration,
                    'best_snp': best_snp_id,
                    'best_p': best_p,
                    'conditioning_snps': selected_snps.copy(),
                    'n_variants_tested': len(results_df),
                    'assoc_file': assoc_file,
                    'top_10_results': results_df.head(10).to_dict('records')
                }
                self.iteration_results.append(iteration_info)
                
                if self.verbose:
                    print(f"{std_INFO}Best candidate: {best_snp_id} (P = {best_p:.2e})")
                    print(f"{std_INFO}Variants tested: {len(results_df)}")
                
                # Check significance threshold
                if best_p < self.significance_threshold:
                    selected_snps.append(best_snp_id)
                    print(f"{std_INFO}✓ Added {best_snp_id} to model (P = {best_p:.2e})")
                    
                    # Check for genome-wide significance
                    if best_p < self.genome_wide_threshold:
                        print(f"{std_INFO}★ Genome-wide significant!")
                else:
                    print(f"{std_INFO}✗ Stopping: Best P-value {best_p:.2e} >= threshold {self.significance_threshold}")
                    break
                    
            except Exception as e:
                print(f"{std_ERROR}Error at iteration {iteration}: {e}")
                break
        
        # Store final results
        self.selected_snps = selected_snps
        end_time = time.time()
        
        # Generate final summary
        final_summary = {
            'analysis_type': 'Stepwise Conditional Regression',
            'regression_type': self.regression_type,
            'phenotype_type': self.phenotype_type,
            'total_iterations': iteration,
            'selected_snps': selected_snps,
            'n_selected_snps': len(selected_snps),
            'significance_threshold': self.significance_threshold,
            'genome_wide_threshold': self.genome_wide_threshold,
            'analysis_region': {
                'chromosome': self.chr_filter,
                'from_mb': self.from_mb,
                'to_mb': self.to_mb,
                'hla_region': self.hla_region
            },
            'execution_time': end_time - start_time,
            'timestamp': datetime.now().isoformat(),
            'iteration_details': self.iteration_results
        }
        
        self.final_results = final_summary
        
        # Save results
        self._save_results()
        
        # Print summary
        self._print_final_summary()
        
        return final_summary
    
    def _save_results(self):
        """Save analysis results to files."""
        if not self.final_results:
            return
        
        # Save JSON summary
        json_file = f"{self.output_prefix}_stepwise_summary.json"
        with open(json_file, 'w') as f:
            json.dump(self.final_results, f, indent=2, default=str)
        
        # Save selected SNPs list
        if self.selected_snps:
            snps_file = f"{self.output_prefix}_selected_snps.txt"
            with open(snps_file, 'w') as f:
                f.write("# Selected SNPs from Stepwise Conditional Regression\n")
                f.write("# Analysis completed: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S") + "\n")
                f.write(f"# Regression type: {self.regression_type}\n")
                f.write(f"# Total SNPs selected: {len(self.selected_snps)}\n")
                f.write("SNP\n")
                for snp in self.selected_snps:
                    f.write(f"{snp}\n")
        
        # Save detailed iteration results
        if self.iteration_results:
            iter_df = pd.DataFrame([
                {
                    'Iteration': r['iteration'],
                    'Best_SNP': r['best_snp'],
                    'P_value': r['best_p'],
                    'Variants_Tested': r['n_variants_tested'],
                    'Conditioning_SNPs': ';'.join(r['conditioning_snps']) if r['conditioning_snps'] else 'None'
                }
                for r in self.iteration_results
            ])
            iter_file = f"{self.output_prefix}_iteration_history.csv"
            iter_df.to_csv(iter_file, index=False)
        
        if self.verbose:
            print(f"{std_INFO}Results saved:")
            print(f"{std_INFO}  - Summary: {json_file}")
            if self.selected_snps:
                print(f"{std_INFO}  - Selected SNPs: {snps_file}")
            if self.iteration_results:
                print(f"{std_INFO}  - Iteration history: {iter_file}")
    
    def _print_final_summary(self):
        """Print final analysis summary."""
        if not self.final_results:
            return
        
        print(f"\n{std_MAIN}STEPWISE CONDITIONAL REGRESSION COMPLETED")
        print("=" * 60)
        print(f"Regression type:        {self.final_results['regression_type']}")
        print(f"Phenotype type:         {self.final_results['phenotype_type']}")
        print(f"Total iterations:       {self.final_results['total_iterations']}")
        print(f"Selected SNPs:          {self.final_results['n_selected_snps']}")
        print(f"Execution time:         {self.final_results['execution_time']:.2f} seconds")
        
        if self.final_results['analysis_region']['hla_region']:
            print(f"Analysis region:        HLA region (Chr{self.final_results['analysis_region']['chromosome']}:{self.final_results['analysis_region']['from_mb']}-{self.final_results['analysis_region']['to_mb']}Mb)")
        
        if self.selected_snps:
            print(f"\nSelected SNPs:")
            for i, snp in enumerate(self.selected_snps, 1):
                # Find the iteration where this SNP was selected
                iter_info = next((r for r in self.iteration_results if r['best_snp'] == snp), None)
                if iter_info:
                    print(f"  {i:2d}. {snp:20s} (P = {iter_info['best_p']:.2e})")
                else:
                    print(f"  {i:2d}. {snp}")
        else:
            print(f"\nNo SNPs met the significance threshold ({self.significance_threshold})")
        
        print("=" * 60)
    
    def get_final_model_results(self) -> Optional[pd.DataFrame]:
        """
        Get the final model results with all selected SNPs.
        
        Returns:
            pd.DataFrame: Final association results or None if no SNPs selected
        """
        if not self.selected_snps:
            return None
        
        # Run final analysis with all selected SNPs
        try:
            final_assoc_file = self._run_plink_association(
                iteration=999,  # Special iteration number for final model
                condition_snps=self.selected_snps[:-1]  # Condition on all but the last SNP
            )
            
            final_results = self._parse_association_results(final_assoc_file)
            return final_results
            
        except Exception as e:
            print(f"{std_WARNING}Could not generate final model results: {e}")
            return None
    
    def cleanup_intermediate_files(self):
        """Remove intermediate files generated during analysis."""
        if self.verbose:
            print(f"{std_INFO}Cleaning up intermediate files...")
        
        # Pattern for intermediate files
        patterns = [
            f"{self.output_prefix}_iter*.log",
            f"{self.output_prefix}_iter*.nosex",
            f"{self.output_prefix}_conditions_iter*.txt",
            f"{self.output_prefix}_iter*.assoc.logistic",
            f"{self.output_prefix}_iter*.assoc.linear"
        ]
        
        import glob
        removed_count = 0
        for pattern in patterns:
            for file_path in glob.glob(pattern):
                try:
                    os.remove(file_path)
                    removed_count += 1
                except Exception as e:
                    if self.verbose:
                        print(f"{std_WARNING}Could not remove {file_path}: {e}")
        
        if self.verbose:
            print(f"{std_INFO}Removed {removed_count} intermediate files")


def run_stepwise_conditional_analysis(bfile_prefix: str,
                                    output_prefix: str,
                                    pheno_file: Optional[str] = None,
                                    pheno_name: Optional[str] = None,
                                    covar_file: Optional[str] = None,
                                    covar_names: Optional[List[str]] = None,
                                    significance_threshold: float = 0.05,
                                    hla_region: bool = True,
                                    cleanup: bool = True,
                                    **kwargs) -> Dict[str, Any]:
    """
    Convenience function to run stepwise conditional regression.
    
    Args:
        bfile_prefix: Prefix for PLINK binary files
        output_prefix: Output prefix for results
        pheno_file: Phenotype file (optional)
        pheno_name: Phenotype column name
        covar_file: Covariate file
        covar_names: Covariate column names
        significance_threshold: P-value threshold for selection
        hla_region: Focus on HLA region
        cleanup: Remove intermediate files
        **kwargs: Additional arguments for StepwiseConditionalRegression
    
    Returns:
        Dict[str, Any]: Analysis results
    """
    # Initialize analysis
    analysis = StepwiseConditionalRegression(
        bfile_prefix=bfile_prefix,
        output_prefix=output_prefix,
        pheno_file=pheno_file,
        pheno_name=pheno_name,
        covar_file=covar_file,
        covar_names=covar_names,
        significance_threshold=significance_threshold,
        hla_region=hla_region,
        **kwargs
    )
    
    # Run analysis
    results = analysis.run_stepwise_analysis()
    
    # Cleanup if requested
    if cleanup:
        analysis.cleanup_intermediate_files()
    
    return results


# Example usage and testing
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Stepwise Conditional Regression using PLINK",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Basic usage with .fam phenotype
    python StepCon_SmartRegression.py --bfile data/mydata --out results/stepwise
    
    # With external phenotype file
    python StepCon_SmartRegression.py --bfile data/mydata --pheno data/pheno.phe --pheno-name DISEASE --out results/stepwise
    
    # With covariates
    python StepCon_SmartRegression.py --bfile data/mydata --pheno data/pheno.phe --covar data/covar.txt --covar-names PC1,PC2,PC3 --out results/stepwise
    
    # Focus on specific region
    python StepCon_SmartRegression.py --bfile data/mydata --out results/stepwise --chr 6 --from-mb 25 --to-mb 35
        """
    )
    
    parser.add_argument('--bfile', required=True, help='PLINK binary file prefix')
    parser.add_argument('--out', required=True, help='Output prefix')
    parser.add_argument('--pheno', help='Phenotype file')
    parser.add_argument('--pheno-name', help='Phenotype column name')
    parser.add_argument('--covar', help='Covariate file')
    parser.add_argument('--covar-names', help='Comma-separated covariate names')
    parser.add_argument('--plink', default='plink', help='PLINK executable path')
    parser.add_argument('--threshold', type=float, default=0.05, help='Significance threshold')
    parser.add_argument('--gwas-threshold', type=float, default=5e-8, help='Genome-wide significance threshold')
    parser.add_argument('--max-iter', type=int, default=100, help='Maximum iterations')
    parser.add_argument('--chr', type=int, help='Chromosome to analyze')
    parser.add_argument('--from-mb', type=float, help='Start position (Mb)')
    parser.add_argument('--to-mb', type=float, help='End position (Mb)')
    parser.add_argument('--no-hla', action='store_true', help='Disable HLA region focus')
    parser.add_argument('--no-cleanup', action='store_true', help='Keep intermediate files')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')
    
    args = parser.parse_args()
    
    # Parse covariate names
    covar_names = None
    if args.covar_names:
        covar_names = [name.strip() for name in args.covar_names.split(',')]
    
    # Run analysis
    try:
        results = run_stepwise_conditional_analysis(
            bfile_prefix=args.bfile,
            output_prefix=args.out,
            pheno_file=args.pheno,
            pheno_name=args.pheno_name,
            covar_file=args.covar,
            covar_names=covar_names,
            plink_path=args.plink,
            significance_threshold=args.threshold,
            genome_wide_threshold=args.gwas_threshold,
            max_iterations=args.max_iter,
            chr_filter=args.chr,
            from_mb=args.from_mb,
            to_mb=args.to_mb,
            hla_region=not args.no_hla,
            verbose=args.verbose,
            cleanup=not args.no_cleanup
        )
        
        print(f"\n✅ Analysis completed successfully!")
        print(f"Selected {results['n_selected_snps']} SNPs in {results['total_iterations']} iterations")
        
    except Exception as e:
        print(f"\n❌ Analysis failed: {e}")
        sys.exit(1) 