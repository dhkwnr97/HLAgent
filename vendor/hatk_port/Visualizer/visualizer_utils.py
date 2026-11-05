#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
visualizer_utils.py
===================
Utility functions for HATK visualizations including Manhattan plots.

This module provides comprehensive helper functions for processing and preparing data
for visualization in the HLAgent HATK pipeline, with support for HLA-specific analysis.

Author: HLAgent Development Team
Date: 2025
"""

import re
import numpy as np
import pandas as pd
from typing import Tuple, Dict, List, Optional, Union
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# HLA gene positions on chromosome 6 (hg18)
HLA_POSITIONS = {
    'HLA_A': 30018000,
    'HLA_B': 31430000,
    'HLA_C': 31345000,
    'HLA_DRB1': 32551000,
    'HLA_DQA1': 32720000,
    'HLA_DQB1': 32740000,
    'HLA_DPA1': 33090000,
    'HLA_DPB1': 33120000
}

# Extended color scheme for different marker types
MARKER_COLORS = {
    'HLA_Allele': '#FFD700',      # Gold for HLA alleles
    'AA': '#FF0000',              # Red for amino acid markers
    'DNA_Intragenic': '#696969',  # Dark grey for intragenic DNA markers
    'DNA_Intergenic': '#D3D3D3',  # Light grey for intergenic DNA markers
    'dbSNP': '#4169E1',           # Royal blue for dbSNP markers
    'Insertion': '#FF8C00',       # Dark orange for insertion markers
    'Unknown': '#808080'          # Grey for unknown markers
}

def validate_input_file(file_path: str, expected_format: str) -> bool:
    """
    Validate input file format and existence.
    
    Args:
        file_path: Path to input file
        expected_format: Expected format ('logistic' or 'omnibus')
        
    Returns:
        True if file is valid, raises exception otherwise
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")
    
    if not path.is_file():
        raise ValueError(f"Path is not a file: {file_path}")
    
    # Check file extension
    if expected_format == 'logistic' and not str(path).endswith('.logistic'):
        logger.warning(f"File doesn't have .logistic extension: {file_path}")
    elif expected_format == 'omnibus' and not str(path).endswith('.omnibus'):
        logger.warning(f"File doesn't have .omnibus extension: {file_path}")
    
    return True

def categorize_marker(marker: str) -> Tuple[str, str]:
    """
    Enhanced marker categorization based on naming patterns.
    
    Args:
        marker: Marker name (e.g., 'HLA_A*01:01', 'AA_A_9_30018537_F', 'SNPS_A_30018457')
        
    Returns:
        Tuple of (category, color) where:
        - category: marker type classification
        - color: Color code for the marker type
    """
    # Handle HLA allele markers
    if re.match(r'HLA_[A-Z0-9]+\*', marker):
        return 'HLA_Allele', MARKER_COLORS['HLA_Allele']
    
    # Handle amino acid markers
    if marker.startswith('AA_') or re.match(r'AA_[A-Z0-9]+_', marker):
        return 'AA', MARKER_COLORS['AA']
    
    # Handle insertion markers
    if marker.startswith('INS_AA_') or marker.startswith('INS_'):
        return 'Insertion', MARKER_COLORS['Insertion']
    
    # Handle intragenic DNA markers
    if marker.startswith('SNPS_') or re.match(r'DNA_[A-Z0-9]+_', marker):
        return 'DNA_Intragenic', MARKER_COLORS['DNA_Intragenic']
    
    # Handle dbSNP markers
    if marker.startswith('rs') or marker.startswith('SNP_A-'):
        return 'dbSNP', MARKER_COLORS['dbSNP']
    
    # Default classification
    logger.debug(f"Unknown marker pattern: {marker}")
    return 'Unknown', MARKER_COLORS['Unknown']

def prepare_logistic_data(file_path: str) -> pd.DataFrame:
    """
    Enhanced preparation of logistic regression data for Manhattan plot.
    
    Args:
        file_path: Path to .assoc.logistic file
        
    Returns:
        DataFrame with columns: CHR, BP, SNP, P, -log10P, color, category
    """
    try:
        validate_input_file(file_path, 'logistic')
        
        # Read the logistic regression file with robust parsing
        df = pd.read_csv(file_path, sep=r'\s+', header=0, na_values=['NA', 'nan', 'NaN'])
        
        # Validate required columns
        required_columns = ['CHR', 'SNP', 'BP', 'P']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Clean data
        df = df.dropna(subset=['P'])  # Remove rows with missing P-values
        df = df[df['P'] > 0]  # Remove non-positive P-values
        
        # Calculate -log10(P)
        df['-log10P'] = -np.log10(df['P'])
        
        # Add marker categories and colors
        df['category'], df['color'] = zip(*df['SNP'].apply(categorize_marker))
        
        # Handle infinite values (very small p-values)
        max_log10p = 320  # Reasonable upper limit
        df['-log10P'] = df['-log10P'].replace([np.inf, -np.inf], max_log10p)
        df['-log10P'] = df['-log10P'].clip(upper=max_log10p)
        
        # Sort by chromosome and position
        df = df.sort_values(['CHR', 'BP'])
        
        logger.info(f"Loaded {len(df)} markers from {file_path}")
        logger.info(f"Marker distribution: {df['category'].value_counts().to_dict()}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading logistic file {file_path}: {str(e)}")
        raise

def prepare_omnibus_data(file_path: str) -> pd.DataFrame:
    """
    Enhanced preparation of omnibus test data for Manhattan plot.
    
    Args:
        file_path: Path to .omnibus file
        
    Returns:
        DataFrame with columns: Variant, log10_P, -log10P, color, category, position
    """
    try:
        validate_input_file(file_path, 'omnibus')
        
        # Read the omnibus file
        df = pd.read_csv(file_path, sep='\t', header=0, na_values=['NA', 'nan', 'NaN'])
        
        # Validate required columns
        required_columns = ['Variant', 'log10_P']
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")
        
        # Clean data
        df = df.dropna(subset=['log10_P'])
        
        # Convert log10_P to -log10P (omnibus already has log10 values, but negative)
        df['-log10P'] = -df['log10_P']
        
        # Add marker categories and colors
        df['category'], df['color'] = zip(*df['Variant'].apply(categorize_marker))
        
        # Extract position information from variant names
        df['position'] = df['Variant'].apply(extract_position_from_variant)
        
        # Sort by position
        df = df.sort_values('position')
        
        logger.info(f"Loaded {len(df)} variants from {file_path}")
        logger.info(f"Variant distribution: {df['category'].value_counts().to_dict()}")
        
        return df
        
    except Exception as e:
        logger.error(f"Error loading omnibus file {file_path}: {str(e)}")
        raise

def extract_position_from_variant(variant: str) -> int:
    """
    Enhanced extraction of position information from omnibus variant names.
    
    Args:
        variant: Variant name (e.g., 'AA_A_9', 'INS_AA_C_300x301_31345772')
        
    Returns:
        Position as integer (genomic position or relative position for visualization)
    """
    # Pattern for INS variants with explicit genomic position
    ins_pattern = re.compile(r'INS_AA_([A-Z0-9]+)_\d+x\d+_(\d+)')
    match = ins_pattern.search(variant)
    if match:
        gene = match.group(1)
        position = int(match.group(2))
        logger.debug(f"INS variant {variant}: gene={gene}, position={position}")
        return position
    
    # Pattern for regular AA variants with gene and position
    aa_pattern = re.compile(r'AA_([A-Z0-9]+)_(-?\d+)')
    match = aa_pattern.search(variant)
    if match:
        gene = match.group(1)
        aa_position = int(match.group(2))
        
        # Map to genomic coordinates based on HLA gene
        if gene in ['A', 'HLA_A']:
            base_pos = HLA_POSITIONS.get('HLA_A', 30018000)
        elif gene in ['B', 'HLA_B']:
            base_pos = HLA_POSITIONS.get('HLA_B', 31430000)
        elif gene in ['C', 'HLA_C']:
            base_pos = HLA_POSITIONS.get('HLA_C', 31345000)
        elif gene in ['DRB1', 'HLA_DRB1']:
            base_pos = HLA_POSITIONS.get('HLA_DRB1', 32551000)
        elif gene in ['DQA1', 'HLA_DQA1']:
            base_pos = HLA_POSITIONS.get('HLA_DQA1', 32720000)
        elif gene in ['DQB1', 'HLA_DQB1']:
            base_pos = HLA_POSITIONS.get('HLA_DQB1', 32740000)
        elif gene in ['DPA1', 'HLA_DPA1']:
            base_pos = HLA_POSITIONS.get('HLA_DPA1', 33090000)
        elif gene in ['DPB1', 'HLA_DPB1']:
            base_pos = HLA_POSITIONS.get('HLA_DPB1', 33120000)
        else:
            base_pos = 31000000  # Default position for unknown genes
        
        # Calculate position: base + (amino acid position * 3 * 10)
        # Factor of 3 for codons, factor of 10 for spacing
        position = base_pos + (aa_position * 30)
        
        logger.debug(f"AA variant {variant}: gene={gene}, aa_pos={aa_position}, genomic_pos={position}")
        return position
    
    # Pattern for HLA allele variants
    hla_allele_pattern = re.compile(r'HLA_([A-Z0-9]+)')
    match = hla_allele_pattern.search(variant)
    if match:
        gene = match.group(1)
        hla_gene_key = f"HLA_{gene}"
        position = HLA_POSITIONS.get(hla_gene_key, 31000000)
        logger.debug(f"HLA allele variant {variant}: gene={gene}, position={position}")
        return position
    
    # Default position for unrecognized patterns
    logger.debug(f"Unrecognized variant pattern: {variant}, using default position")
    return 31000000

def calculate_genomic_positions(df: pd.DataFrame) -> Tuple[pd.DataFrame, Dict[int, int]]:
    """
    Enhanced calculation of cumulative genomic positions for Manhattan plot x-axis.
    
    Args:
        df: DataFrame with CHR and BP columns
        
    Returns:
        Tuple of (DataFrame with 'pos_cum' column, chromosome start positions dict)
    """
    try:
        # Calculate chromosome lengths with some padding
        chr_lengths = df.groupby('CHR')['BP'].max().to_dict()
        
        # Calculate cumulative positions with spacing between chromosomes
        chr_start = {}
        cum_pos = 0
        spacing = 5000000  # 5Mb spacing between chromosomes
        
        for chr_num in sorted(df['CHR'].unique()):
            chr_start[chr_num] = cum_pos
            cum_pos += chr_lengths.get(chr_num, 0) + spacing
        
        # Add cumulative position column
        df['pos_cum'] = df.apply(lambda row: chr_start[row['CHR']] + row['BP'], axis=1)
        
        logger.debug(f"Calculated cumulative positions for {len(chr_start)} chromosomes")
        
        return df, chr_start
        
    except Exception as e:
        logger.error(f"Error calculating genomic positions: {str(e)}")
        raise

def get_significance_thresholds() -> Dict[str, float]:
    """
    Get standard GWAS significance thresholds.
    
    Returns:
        Dictionary with suggestive and genome-wide significance thresholds
    """
    return {
        'suggestive': -np.log10(1e-5),      # Suggestive significance
        'genome_wide': -np.log10(5e-8),     # Genome-wide significance
        'moderate': -np.log10(1e-3),        # Moderate significance
        'nominal': -np.log10(0.05)          # Nominal significance
    }

def format_hover_text(row: pd.Series, plot_type: str) -> str:
    """
    Enhanced hover text formatting for interactive plot tooltips.
    
    Args:
        row: DataFrame row
        plot_type: 'regression' or 'omnibus'
        
    Returns:
        Formatted hover text string
    """
    if plot_type == 'regression':
        hover_parts = [
            f"<b>SNP:</b> {row['SNP']}",
            f"<b>Chromosome:</b> {row['CHR']}",
            f"<b>Position:</b> {row['BP']:,}",
            f"<b>P-value:</b> {row['P']:.2e}",
            f"<b>-log10(P):</b> {row['-log10P']:.2f}",
            f"<b>Type:</b> {row['category']}"
        ]
        
        # Add additional info if available
        if 'OR' in row and pd.notna(row['OR']):
            hover_parts.append(f"<b>Odds Ratio:</b> {row['OR']:.3f}")
        if 'SE' in row and pd.notna(row['SE']):
            hover_parts.append(f"<b>Std Error:</b> {row['SE']:.3f}")
            
        return "<br>".join(hover_parts)
        
    else:  # omnibus
        hover_parts = [
            f"<b>Variant:</b> {row['Variant']}",
            f"<b>P-value:</b> {10**row['log10_P']:.2e}",
            f"<b>-log10(P):</b> {row['-log10P']:.2f}",
            f"<b>Type:</b> {row['category']}"
        ]
        
        # Add additional info if available
        if 'deltaDeviance' in row and pd.notna(row['deltaDeviance']):
            hover_parts.append(f"<b>Delta Deviance:</b> {row['deltaDeviance']:.2f}")
        if 'deltaDF' in row and pd.notna(row['deltaDF']):
            hover_parts.append(f"<b>Delta DF:</b> {int(row['deltaDF'])}")
        if 'Residues' in row and pd.notna(row['Residues']):
            hover_parts.append(f"<b>Residues:</b> {row['Residues']}")
            
        return "<br>".join(hover_parts)

def filter_top_signals(df: pd.DataFrame, threshold: float = 0.05, max_points: int = 100000) -> pd.DataFrame:
    """
    Enhanced filtering of data to include significant signals and random sampling for performance.
    
    Args:
        df: DataFrame with P-values
        threshold: P-value threshold (default 0.05)
        max_points: Maximum number of points to plot for performance
        
    Returns:
        Filtered DataFrame
    """
    try:
        # First, get all significant signals
        if 'P' in df.columns:
            significant = df[df['P'] <= threshold]
            non_significant = df[df['P'] > threshold]
        elif 'log10_P' in df.columns:
            log_threshold = np.log10(threshold)
            significant = df[df['log10_P'] <= log_threshold]
            non_significant = df[df['log10_P'] > log_threshold]
        else:
            logger.warning("No P-value column found, returning original data")
            return df
        
        # If we have too many points, sample the non-significant ones
        total_significant = len(significant)
        remaining_budget = max_points - total_significant
        
        if remaining_budget > 0 and len(non_significant) > remaining_budget:
            # Sample non-significant points, keeping some from each category if possible
            if 'category' in non_significant.columns:
                sampled_parts = []
                categories = non_significant['category'].unique()
                points_per_category = max(1, remaining_budget // len(categories))
                
                for category in categories:
                    category_data = non_significant[non_significant['category'] == category]
                    sample_size = min(len(category_data), points_per_category)
                    sampled_parts.append(category_data.sample(n=sample_size, random_state=42))
                
                non_significant_sampled = pd.concat(sampled_parts, ignore_index=True)
            else:
                non_significant_sampled = non_significant.sample(n=remaining_budget, random_state=42)
        else:
            non_significant_sampled = non_significant
        
        # Combine significant and sampled non-significant
        result = pd.concat([significant, non_significant_sampled], ignore_index=True)
        
        logger.info(f"Filtered data: {len(significant)} significant + {len(non_significant_sampled)} sampled = {len(result)} total points")
        
        return result
        
    except Exception as e:
        logger.error(f"Error filtering signals: {str(e)}")
        return df

def optimize_data_for_plotting(df: pd.DataFrame, plot_type: str = 'regression') -> pd.DataFrame:
    """
    Optimize data for plotting by removing redundant points and ensuring good performance.
    
    Args:
        df: Input DataFrame
        plot_type: Type of plot ('regression' or 'omnibus')
        
    Returns:
        Optimized DataFrame
    """
    try:
        original_size = len(df)
        
        # Remove duplicate positions (keep the most significant)
        if plot_type == 'regression' and 'BP' in df.columns:
            df = df.sort_values(['-log10P'], ascending=False)
            df = df.drop_duplicates(subset=['CHR', 'BP'], keep='first')
        elif plot_type == 'omnibus' and 'position' in df.columns:
            df = df.sort_values(['-log10P'], ascending=False)
            df = df.drop_duplicates(subset=['position'], keep='first')
        
        # Sort for better plotting performance
        if plot_type == 'regression':
            df = df.sort_values(['CHR', 'BP'])
        else:
            df = df.sort_values(['position'])
        
        optimized_size = len(df)
        logger.info(f"Optimized data: {original_size} -> {optimized_size} points")
        
        return df
        
    except Exception as e:
        logger.error(f"Error optimizing data: {str(e)}")
        return df

def generate_plot_summary(df: pd.DataFrame, plot_type: str) -> Dict[str, any]:
    """
    Generate summary statistics for the plot data.
    
    Args:
        df: Input DataFrame
        plot_type: Type of plot ('regression' or 'omnibus')
        
    Returns:
        Dictionary with summary statistics
    """
    try:
        summary = {
            'total_markers': len(df),
            'marker_types': df['category'].value_counts().to_dict(),
            'min_log10p': df['-log10P'].min(),
            'max_log10p': df['-log10P'].max(),
            'mean_log10p': df['-log10P'].mean(),
            'median_log10p': df['-log10P'].median()
        }
        
        # Add plot-specific statistics
        if plot_type == 'regression':
            summary['chromosomes'] = sorted(df['CHR'].unique().tolist())
            summary['position_range'] = {
                'min': df['BP'].min(),
                'max': df['BP'].max()
            }
            if 'P' in df.columns:
                thresholds = get_significance_thresholds()
                summary['significant_markers'] = {
                    'genome_wide': len(df[df['P'] <= 5e-8]),
                    'suggestive': len(df[df['P'] <= 1e-5]),
                    'nominal': len(df[df['P'] <= 0.05])
                }
        else:  # omnibus
            summary['position_range'] = {
                'min': df['position'].min(),
                'max': df['position'].max()
            }
            if 'log10_P' in df.columns:
                thresholds = get_significance_thresholds()
                summary['significant_variants'] = {
                    'genome_wide': len(df[df['log10_P'] <= np.log10(5e-8)]),
                    'suggestive': len(df[df['log10_P'] <= np.log10(1e-5)]),
                    'nominal': len(df[df['log10_P'] <= np.log10(0.05)])
                }
        
        return summary
        
    except Exception as e:
        logger.error(f"Error generating plot summary: {str(e)}")
        return {'error': str(e)}
