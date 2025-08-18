#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
metaanal_utils.py
=================
Core utility functions for HLA meta-analysis using inverse-variance weighting method.

This module provides functions for:
- Reading and validating logistic regression results
- Reading and validating marker information files
- Allele flipping between studies
- Inverse-variance weighted meta-analysis
- Output formatting

Author: HLAgent Development Team
Date: 2025
"""

import os
import sys
import re
import pandas as pd
import numpy as np
from math import log
from scipy.stats import norm
from typing import Tuple, Dict, Any, Optional, Union
from pathlib import Path


# Complement base mapping for allele flipping
COMPLEMENT_BASE = {
    'A': 'T',
    'T': 'A',
    'C': 'G',
    'G': 'C'
}


class MetaAnalysisError(Exception):
    """Custom exception for meta-analysis errors."""
    pass


def read_logistic_result(filepath: str) -> pd.DataFrame:
    """
    Read and validate logistic regression result file.
    
    Args:
        filepath: Path to logistic regression result file
        
    Returns:
        DataFrame with columns: SNP, BETA, SE, OR (if available)
        
    Raises:
        MetaAnalysisError: If file format is invalid or required columns missing
    """
    if not os.path.exists(filepath):
        raise MetaAnalysisError(f"Logistic regression result file not found: {filepath}")
    
    try:
        if filepath.endswith('.assoc.logistic'):
            # Standard PLINK logistic regression result
            df = pd.read_csv(filepath, sep=r'\s+', header=0, engine='python')

            # Check required columns
            required_cols = ['SNP', 'OR', 'SE']
            if not all(col in df.columns for col in required_cols):
                raise MetaAnalysisError(f"Missing required columns in {filepath}. Required: {required_cols}, Found: {list(df.columns)}")
            
            # Remove NA rows
            df = df.dropna(subset=['SNP', 'OR', 'SE'])
            
            # Calculate BETA from OR
            df['BETA'] = df['OR'].apply(lambda x: log(x) if x > 0 else np.nan)
            df = df.dropna(subset=['BETA'])
            
            return df[['SNP', 'BETA', 'SE', 'OR']]
            
        else:
            # Try to read as generic tab/space separated file
            df = pd.read_csv(filepath, sep=r'\s+', header=0, engine='python')
            
            # Check what columns we have
            if 'SNP' not in df.columns:
                raise MetaAnalysisError(f"Column 'SNP' not found in {filepath}")
            
            # Need either BETA or OR
            if 'BETA' not in df.columns and 'OR' not in df.columns:
                raise MetaAnalysisError(f"Neither 'BETA' nor 'OR' column found in {filepath}")
            
            # Need either SE or P
            if 'SE' not in df.columns and 'P' not in df.columns:
                raise MetaAnalysisError(f"Neither 'SE' nor 'P' column found in {filepath}")
            
            # Calculate missing values
            if 'BETA' not in df.columns and 'OR' in df.columns:
                df['BETA'] = df['OR'].apply(lambda x: log(x) if x > 0 else np.nan)
            
            if 'SE' not in df.columns and 'P' in df.columns and 'BETA' in df.columns:
                # Back-calculate SE from P-value and BETA
                df['SE'] = abs(df['BETA'] / norm.ppf(df['P'] / 2))
            
            # Clean up
            df = df.dropna(subset=['SNP', 'BETA', 'SE'])
            
            result_cols = ['SNP', 'BETA', 'SE']
            if 'OR' in df.columns:
                result_cols.append('OR')
                
            return df[result_cols]
            
    except Exception as e:
        raise MetaAnalysisError(f"Error reading logistic regression file {filepath}: {str(e)}")


def read_marker_file(filepath: str) -> pd.DataFrame:
    """
    Read marker information file (BIM or markers format).
    
    Args:
        filepath: Path to marker file
        
    Returns:
        DataFrame with columns: SNP, BP, al1, al2
        
    Raises:
        MetaAnalysisError: If file format is invalid
    """
    if not os.path.exists(filepath):
        raise MetaAnalysisError(f"Marker file not found: {filepath}")
    
    try:
        if filepath.endswith('.bim'):
            # PLINK BIM format: CHR SNP GD BP A1 A2
            df = pd.read_csv(filepath, sep=r'\s+', header=None,
                           names=['Chr', 'SNP', 'GD', 'BP', 'al1', 'al2'])
            return df[['SNP', 'BP', 'al1', 'al2']]
            
        elif filepath.endswith('.markers'):
            # HATK markers format: SNP BP A1 A2
            df = pd.read_csv(filepath, sep=r'\s+', header=None,
                           names=['SNP', 'BP', 'al1', 'al2'])
            return df[['SNP', 'BP', 'al1', 'al2']]
            
        else:
            # Try to infer format from first line
            with open(filepath, 'r') as f:
                first_line = f.readline().strip()
                num_cols = len(first_line.split())
                
            if num_cols == 6:
                # Assume BIM format
                df = pd.read_csv(filepath, sep=r'\s+', header=None,
                               names=['Chr', 'SNP', 'GD', 'BP', 'al1', 'al2'])
                return df[['SNP', 'BP', 'al1', 'al2']]
            elif num_cols == 4:
                # Assume markers format
                df = pd.read_csv(filepath, sep=r'\s+', header=None,
                               names=['SNP', 'BP', 'al1', 'al2'])
                return df[['SNP', 'BP', 'al1', 'al2']]
            else:
                raise MetaAnalysisError(f"Unknown marker file format in {filepath}")
                
    except Exception as e:
        raise MetaAnalysisError(f"Error reading marker file {filepath}: {str(e)}")


def flip_alleles(df_merged: pd.DataFrame, study1_markers: pd.DataFrame, 
                study2_markers: pd.DataFrame) -> pd.DataFrame:
    """
    Apply allele flipping logic to align alleles between studies.
    
    Args:
        df_merged: Merged DataFrame with BETA_x, SE_x (study1) and BETA_y, SE_y (study2)
        study1_markers: Marker info for study 1
        study2_markers: Marker info for study 2
        
    Returns:
        DataFrame with flipping applied (BETA_y adjusted if needed)
        
    Raises:
        MetaAnalysisError: If allele mismatch cannot be resolved
    """
    # Merge marker information
    df_markers = study1_markers.merge(study2_markers, on='SNP', suffixes=('_x', '_y'))
    
    # Merge with main data
    df_result = df_merged.merge(df_markers[['SNP', 'al1_x', 'al2_x', 'al1_y', 'al2_y']], 
                               on='SNP', how='left')
    
    # Check if complement is needed
    def needs_complement(row):
        alleles = {row['al1_x'], row['al2_x'], row['al1_y'], row['al2_y']}
        return len(alleles) == 4
    
    df_result['need_complement'] = df_result.apply(needs_complement, axis=1)
    
    # Apply flipping logic
    flip_count = 0
    error_snps = []
    
    for idx, row in df_result.iterrows():
        if pd.isna(row['al1_x']) or pd.isna(row['al1_y']):
            continue
            
        al1_x, al2_x = row['al1_x'], row['al2_x']
        al1_y, al2_y = row['al1_y'], row['al2_y']
        
        # Apply complement if needed
        if row['need_complement']:
            al1_y = COMPLEMENT_BASE.get(al1_y, al1_y)
            al2_y = COMPLEMENT_BASE.get(al2_y, al2_y)
        
        # Check allele alignment
        if al1_x == al1_y and al2_x == al2_y:
            # Alleles match - no flip needed
            pass
        elif al1_x == al2_y and al2_x == al1_y:
            # Alleles flipped - flip beta
            df_result.loc[idx, 'BETA_y'] = -df_result.loc[idx, 'BETA_y']
            flip_count += 1
        else:
            # Allele mismatch
            error_snps.append(row['SNP'])
    
    if error_snps:
        print(f"Warning: {len(error_snps)} SNPs have unresolvable allele mismatches and will be excluded")
        df_result = df_result[~df_result['SNP'].isin(error_snps)]
    
    print(f"Flipped {flip_count} SNPs to align alleles between studies")
    
    return df_result


def inverse_variance_meta_analysis(df_merged: pd.DataFrame) -> pd.DataFrame:
    """
    Perform inverse-variance weighted meta-analysis.
    
    Args:
        df_merged: DataFrame with columns: SNP, BETA_x, SE_x, BETA_y, SE_y
        
    Returns:
        DataFrame with columns: SNP, BETA, SE, MetaP
    """
    # Ensure no division by zero
    np.seterr(divide='ignore', invalid='ignore')
    
    # Calculate weights
    w_study1 = 1 / (df_merged['SE_x'] ** 2)
    w_study2 = 1 / (df_merged['SE_y'] ** 2)
    
    # Get betas
    beta_study1 = df_merged['BETA_x']
    beta_study2 = df_merged['BETA_y']
    
    # Inverse variance weighted effect
    ivw = (beta_study1 * w_study1 + beta_study2 * w_study2) / (w_study1 + w_study2)
    
    # Combined standard error
    ivw_se = np.sqrt(1 / (w_study1 + w_study2))
    
    # Calculate Z-score and P-value
    meta_z = ivw / ivw_se
    meta_p = 2 * norm.cdf(-np.abs(meta_z))
    
    # Create result DataFrame
    result = pd.DataFrame({
        'SNP': df_merged['SNP'],
        'BETA': ivw,
        'SE': ivw_se,
        'MetaP': meta_p
    })
    
    # Remove rows with invalid values
    result = result.replace([np.inf, -np.inf], np.nan)
    result = result.dropna()
    
    return result


def run_meta_analysis(study1_logistic: str, study2_logistic: str,
                     study1_bim: Optional[str] = None, 
                     study2_bim: Optional[str] = None,
                     output_prefix: str = None) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    Run complete meta-analysis pipeline.
    
    Args:
        study1_logistic: Path to study 1 logistic regression results
        study2_logistic: Path to study 2 logistic regression results
        study1_bim: Optional path to study 1 marker file
        study2_bim: Optional path to study 2 marker file
        output_prefix: Output file prefix (if None, returns DataFrame only)
        
    Returns:
        Tuple of (result_dataframe, summary_dict)
    """
    print("Starting meta-analysis...")
    
    # Read logistic regression results
    print("Reading study 1 results...")
    df_study1 = read_logistic_result(study1_logistic)
    print(f"  - Found {len(df_study1)} variants in study 1")
    
    print("Reading study 2 results...")
    df_study2 = read_logistic_result(study2_logistic)
    print(f"  - Found {len(df_study2)} variants in study 2")
    
    # Merge on common SNPs
    df_merged = df_study1.merge(df_study2, on='SNP', suffixes=('_x', '_y'))
    print(f"  - Found {len(df_merged)} common variants")
    
    # Apply allele flipping if marker files provided
    if study1_bim and study2_bim:
        print("Reading marker information...")
        markers1 = read_marker_file(study1_bim)
        markers2 = read_marker_file(study2_bim)
        
        print("Checking allele alignment...")
        df_merged = flip_alleles(df_merged, markers1, markers2)
    
    # Perform meta-analysis
    print("Performing inverse-variance weighted meta-analysis...")
    df_result = inverse_variance_meta_analysis(df_merged)
    
    # Generate summary statistics
    summary = {
        'study1_variants': len(df_study1),
        'study2_variants': len(df_study2),
        'common_variants': len(df_merged),
        'analyzed_variants': len(df_result),
        'significant_variants': len(df_result[df_result['MetaP'] < 0.05]),
        'highly_significant_variants': len(df_result[df_result['MetaP'] < 5e-8])
    }
    
    # Save results if output prefix provided
    if output_prefix:
        output_file = f"{output_prefix}.meta"
        df_result.to_csv(output_file, sep='\t', index=False)
        print(f"Results saved to: {output_file}")
        summary['output_file'] = output_file
    
    print(f"\nMeta-analysis complete!")
    print(f"  - Analyzed {summary['analyzed_variants']} variants")
    print(f"  - Significant variants (P < 0.05): {summary['significant_variants']}")
    print(f"  - Highly significant variants (P < 5e-8): {summary['highly_significant_variants']}")
    
    return df_result, summary
