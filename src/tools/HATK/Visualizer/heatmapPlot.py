#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
heatmapPlot_v2.py
=================
Enhanced HLA Heatmap visualization module for HATK analysis results.

This module generates interactive and static heatmaps from HLA association analysis
results, replicating and extending the functionality of the original HATK heatmapPlot.

Features:
- Supports both plotly (interactive) and matplotlib (static) visualizations
- Generates intermediate files compatible with HATK format
- Comprehensive logging and error handling
- Configurable visualization parameters
- Memory-efficient processing for large datasets

Author: HLAgent Development Team
Date: 2025
"""

import os
import re
import time
import warnings
from math import log10
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Tuple, Union, Optional

# Data manipulation
import pandas as pd
import numpy as np

# Visualization libraries
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.colors import LinearSegmentedColormap, Normalize
import seaborn as sns

# Optional plotly support
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from plotly.subplots import make_subplots
    import plotly.io as pio
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False
    warnings.warn("Plotly not available. Only matplotlib visualizations will be supported.")

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=FutureWarning)
warnings.filterwarnings('ignore', category=UserWarning)


def validate_input_files(maptable_file: str, assoc_file: str) -> Tuple[bool, str]:
    """
    Validate that required input files exist and are accessible.
    
    Args:
        maptable_file: Path to HLA maptable file
        assoc_file: Path to association results file
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Check maptable file
        if not os.path.exists(maptable_file):
            return False, f"Maptable file not found: {maptable_file}"
        
        if not os.path.isfile(maptable_file):
            return False, f"Maptable path is not a file: {maptable_file}"
        
        # Check association file
        if not os.path.exists(assoc_file):
            return False, f"Association file not found: {assoc_file}"
        
        if not os.path.isfile(assoc_file):
            return False, f"Association path is not a file: {assoc_file}"
        
        # Check file sizes (should not be empty)
        if os.path.getsize(maptable_file) == 0:
            return False, f"Maptable file is empty: {maptable_file}"
        
        if os.path.getsize(assoc_file) == 0:
            return False, f"Association file is empty: {assoc_file}"
        
        return True, "Input files validation successful"
        
    except Exception as e:
        return False, f"Error validating input files: {str(e)}"


def create_plotly_heatmap(
    amino_acid_matrix: pd.DataFrame,
    aa_pvalue_matrix: pd.DataFrame, 
    hla_allele_pvalues: pd.Series,
    output_path: str,
    hla_gene: str,
    max_pvalue_display: float = 15.0
) -> str:
    """
    Create interactive heatmap using plotly.
    
    Args:
        amino_acid_matrix: Amino acid character matrix
        aa_pvalue_matrix: Signed -log10(p) value matrix
        hla_allele_pvalues: HLA allele significance values
        output_path: Output file prefix
        hla_gene: HLA gene name
        max_pvalue_display: The maximum value for the color scale
    
    Returns:
        Path to generated HTML file
    """
    if not PLOTLY_AVAILABLE:
        raise ImportError("Plotly is not available. Please install plotly or use matplotlib.")
    
    try:
        # Prepare data for visualization
        z_values = aa_pvalue_matrix.values
        amino_acids = amino_acid_matrix.values
        
        # Create text annotations combining amino acids and p-values
        text_matrix = []
        for i in range(amino_acids.shape[0]):
            text_row = []
            for j in range(amino_acids.shape[1]):
                aa_char = amino_acids[i, j]
                text_row.append(f"{aa_char}")
            text_matrix.append(text_row)
        
        # Create subplot layout: main heatmap + allele sidebar
        fig = make_subplots(
            rows=1, cols=2,
            column_widths=[0.85, 0.15],
            subplot_titles=[f"HLA-{hla_gene} Amino Acid Associations", "HLA Alleles"],
            horizontal_spacing=0.05
        )
        
        # Main amino acid heatmap
        heatmap = go.Heatmap(
            z=z_values,
            text=text_matrix,
            texttemplate="%{text}",
            textfont={"size": 10},
            x=aa_pvalue_matrix.columns,
            y=aa_pvalue_matrix.index,
            colorscale="RdBu_r",
            zmid=0,
            zmin=-max_pvalue_display,
            zmax=max_pvalue_display,
            colorbar=dict(
                title="Signed -log10(p)",
                orientation='h',
                y=-0.2,
                yanchor='top',
                x=0.425, # Center on the main heatmap (which is 85% wide)
                xanchor='center',
                len=0.85,
                thickness=20
            ),
            hovertemplate="<b>%{y}</b><br>" +
                         "Position: %{x}<br>" +
                         "Amino Acid: %{text}<br>" +
                         "Signed -log10(p): %{z:.3f}<br>" +
                         "<extra></extra>"
        )
        
        fig.add_trace(heatmap, row=1, col=1)
        
        # HLA allele sidebar
        allele_heatmap = go.Heatmap(
            x=["Allele P"],
            z=hla_allele_pvalues.values.reshape(-1, 1),
            y=hla_allele_pvalues.index,
            text=hla_allele_pvalues.index.to_frame().values,
            texttemplate="%{text}",
            textfont={"size": 12},
            colorscale="RdBu_r",
            zmid=0,
            zmin=-max_pvalue_display,
            zmax=max_pvalue_display,
            showscale=False,
            hovertemplate="<b>%{y}</b><br>" +
                         "Signed -log10(p): %{z:.3f}<br>" +
                         "<extra></extra>"
        )
        
        fig.add_trace(allele_heatmap, row=1, col=2)
        
        # Update layout
        fig.update_layout(
            title=f"HLA-{hla_gene} Association Heatmap",
            height=900,
            width=1400,
            font=dict(size=12),
            title_font=dict(size=16),
            margin=dict(b=200)  # Increase bottom margin for colorbar and annotations
        )
        
        fig.add_annotation(
            dict(
                x=0.28, y=-0.18,
                xref='paper', yref='paper',
                text='<b>《《《《《《  Higher Protective 《《《《《《</b>',
                showarrow=True, arrowhead=4,
                ax=50, ay=0
            )
        )
        fig.add_annotation(
            dict(
                x=0.68, y=-0.18,
                xref='paper', yref='paper',
                text='<b> 》》》》》》 Higher Risk  》》》》》》</b>',
                showarrow=True, arrowhead=4,
                ax=-50, ay=0
            )
        )
        
        # Update axes
        fig.update_xaxes(title_text="Amino Acid Position", row=1, col=1)
        fig.update_yaxes(title_text="HLA Alleles", row=1, col=1)
        fig.update_xaxes(title_text="", row=1, col=2)
        fig.update_yaxes(title_text="", row=1, col=2, showticklabels=False)
        
        # Save HTML file
        output_file = f"{output_path}_heatmap.html"
        fig.write_html(output_file)
        
        return output_file
        
    except Exception as e:
        raise Exception(f"Error creating plotly heatmap: {str(e)}")


def create_matplotlib_heatmap(
    amino_acid_matrix: pd.DataFrame,
    aa_pvalue_matrix: pd.DataFrame,
    hla_allele_pvalues: pd.Series,
    output_path: str,
    hla_gene: str,
    max_pvalue_display: float = 15.0
) -> str:
    """
    Create static heatmap using matplotlib.
    
    Args:
        amino_acid_matrix: Amino acid character matrix
        aa_pvalue_matrix: Signed -log10(p) value matrix 
        hla_allele_pvalues: HLA allele significance values
        output_path: Output file prefix
        hla_gene: HLA gene name
        max_pvalue_display: The maximum value for the color scale
    
    Returns:
        Path to generated PNG file
    """
    try:
        # Create figure with adjusted layout for bottom colorbar
        fig = plt.figure(figsize=(14, 10))
        gs = fig.add_gridspec(2, 2, height_ratios=[20, 1], width_ratios=[5, 1],
                              hspace=0.3, wspace=0.05)
        
        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[0, 1], sharey=ax1)
        cbar_ax = fig.add_subplot(gs[1, 0])

        # Main amino acid heatmap
        im1 = ax1.imshow(
            aa_pvalue_matrix.values,
            cmap='RdBu_r',
            aspect='auto',
            vmin=-max_pvalue_display,
            vmax=max_pvalue_display
        )
        
        # Add amino acid text annotations
        for i in range(aa_pvalue_matrix.shape[0]):
            for j in range(aa_pvalue_matrix.shape[1]):
                aa_char = amino_acid_matrix.iloc[i, j]
                pval = aa_pvalue_matrix.iloc[i, j]
                text_color = 'white' if abs(pval) > (max_pvalue_display * 0.5) else 'black'
                ax1.text(j, i, aa_char, ha='center', va='center',
                         color=text_color, fontsize=10, fontweight='bold')
        
        # Configure main heatmap axes
        ax1.set_xticks(range(len(aa_pvalue_matrix.columns)))
        ax1.set_xticklabels(aa_pvalue_matrix.columns, rotation=45, ha='right')
        ax1.set_yticks(range(len(aa_pvalue_matrix.index)))
        ax1.set_yticklabels(aa_pvalue_matrix.index)
        ax1.set_xlabel('Amino Acid Position')
        ax1.set_ylabel('HLA Alleles')
        ax1.set_title(f'HLA-{hla_gene} Amino Acid Associations')
        
        # HLA allele sidebar
        allele_data = hla_allele_pvalues.values.reshape(-1, 1)
        im2 = ax2.imshow(
            allele_data,
            cmap='RdBu_r',
            aspect='auto',
            vmin=-max_pvalue_display,
            vmax=max_pvalue_display
        )
        
        # 3. Add HLA allele names to sidebar
        for i, allele_name in enumerate(hla_allele_pvalues.index):
            pval = hla_allele_pvalues.iloc[i]
            text_color = 'white' if abs(pval) > (max_pvalue_display * 0.5) else 'black'
            ax2.text(0, i, allele_name, ha='center', va='center', fontsize=10, color=text_color)

        # Configure sidebar
        ax2.set_xticks([])
        plt.setp(ax2.get_yticklabels(), visible=False)
        ax2.set_title('Allele P-values')

        # 1. Add colorbar to the bottom
        cbar = fig.colorbar(im1, cax=cbar_ax, orientation='horizontal')
        cbar.set_label('Signed -log10(p)')
        
        # 2. Add annotations for Protective/Risk to the colorbar
        cbar_ax.annotate('Higher Protective', xy=(0, 0.5), xytext=(-0.1, 0.5),
                         arrowprops=dict(facecolor='blue', shrink=0.05, width=1, headwidth=5),
                         xycoords='axes fraction', textcoords='axes fraction',
                         ha='right', va='center', color='blue', fontsize=12)
        
        cbar_ax.annotate('Higher Risk', xy=(1, 0.5), xytext=(1.1, 0.5),
                         arrowprops=dict(facecolor='red', shrink=0.05, width=1, headwidth=5),
                         xycoords='axes fraction', textcoords='axes fraction',
                         ha='left', va='center', color='red', fontsize=12)
        
        # Overall title
        fig.suptitle(f'HLA-{hla_gene} Association Heatmap', fontsize=16, y=0.98)
        
        # Save PNG file
        output_file = f"{output_path}_heatmap.png"
        plt.savefig(output_file, dpi=300, bbox_inches='tight')
        plt.close(fig)
        
        return output_file
        
    except Exception as e:
        raise Exception(f"Error creating matplotlib heatmap: {str(e)}")


class HeatmapGenerator:
    """
    HLA Heatmap Generator for association analysis results.
    
    This class processes HLA association data and maptable files to generate
    comprehensive heatmap visualizations showing amino acid associations.
    """
    
    def __init__(
        self,
        assoc_file: str,
        maptable_file: str,
        hla_gene: str,
        output_prefix: str,
        use_plotly: bool = True,
        save_intermediates: bool = True,
        config: Optional[Dict[str, Any]] = None,
        verbose: bool = True
    ):
        """
        Initialize HeatmapGenerator.
        
        Args:
            assoc_file: Path to association results file
            maptable_file: Path to HLA maptable file
            hla_gene: HLA gene name (e.g., 'A', 'B', 'C')
            output_prefix: Output file prefix for generated files
            use_plotly: Whether to use plotly for interactive visualization
            save_intermediates: Whether to save intermediate files
            config: Configuration dictionary
            verbose: Enable verbose logging
        """
        # Core parameters
        self.assoc_file = assoc_file
        self.maptable_file = maptable_file
        self.hla_gene = hla_gene
        self.output_prefix = output_prefix
        self.use_plotly = use_plotly and PLOTLY_AVAILABLE
        self.save_intermediates = save_intermediates
        self.verbose = verbose
        
        # Configuration
        self.config = config or {}
        self._load_config_parameters()
        
        # Data storage
        self.maptable_df = None
        self.processed_maptable = None
        self.aa_results_df = None
        self.hla_results_df = None
        self.aa_results_indexed = None
        self.aa_pvalue_matrix = None
        self.hla_allele_pvalues = None
        
        # Output tracking
        self.heatmap_file = None
        self.intermediate_files = {}
        self.success = False
        
        # Create output directory if needed
        output_dir = os.path.dirname(self.output_prefix)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
    
    def _load_config_parameters(self) -> None:
        """Load configuration parameters with defaults."""
        # Data processing parameters
        data_config = self.config.get('_data_processing', {})
        
        # convert to float/int
        sig_thresh = data_config.get('significance_threshold', 0.05)
        self.significance_threshold = float(sig_thresh) if sig_thresh is not None else None
        
        self.max_pvalue_display = float(data_config.get('max_pvalue_display', 15))
        self.min_pvalue = float(data_config.get('min_pvalue', 1e-300))
        
        # Figure settings
        figure_config = self.config.get('_figure_settings', {})
        self.figure_width = int(figure_config.get('width', 1400))
        self.figure_height = int(figure_config.get('height', 900))
        self.text_size = int(figure_config.get('text_size', 10))
        self.title_size = int(figure_config.get('title_size', 16))
        self.colorscale = figure_config.get('colorscale', 'RdBu_r')
    
    def _log(self, message: str, level: str = "INFO") -> None:
        """Log messages with timestamp if verbose mode is enabled."""
        if not self.verbose:
            return
        
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if level == "ERROR":
            print(f"[{timestamp} ERROR]: {message}")
        elif level == "WARNING":
            print(f"[{timestamp} WARNING]: {message}")
        else:
            print(f"[{timestamp} INFO]: {message}")
    
    def load_maptable(self) -> bool:
        """
        Load and parse HLA maptable file.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self._log(f"Loading maptable: {self.maptable_file}")
            
            # Read maptable file
            # Format: tab-separated with HLA alleles as rows and positions as columns
            self.maptable_df = pd.read_csv(
                self.maptable_file, 
                sep='\t',
                index_col=0,
                header=[0, 1, 2]  # Multi-level header: (rel_pos, genomic_pos, exon_type)
            )
            
            self._log(f"Loaded maptable with shape: {self.maptable_df.shape}")
            self._log(f"HLA alleles: {len(self.maptable_df.index)}")
            self._log(f"Amino acid positions: {len(self.maptable_df.columns)}")
            
            return True
            
        except Exception as e:
            self._log(f"Error loading maptable: {str(e)}", "ERROR")
            return False
    
    def load_association_results(self) -> bool:
        """
        Load and parse association results, separating AA and HLA markers.
        Replicates HATK's association loading logic.
        """
        try:
            self._log(f"Loading association results: {self.assoc_file}")
            
            # Load association results with required columns
            assoc_df = pd.read_csv(
                self.assoc_file, sep=r'\s+', 
                usecols=['SNP', 'A1', 'OR', 'P'],
                dtype={'SNP': str, 'A1': str, 'OR': float, 'P': float}
            ).dropna()
            
            self._log(f"Loaded {len(assoc_df)} association markers")
            
            # Create patterns for AA and HLA markers
            aa_pattern = re.compile(f"^AA_{self.hla_gene}_")
            hla_pattern = re.compile(f"^HLA_{self.hla_gene}")
            
            # Filter AA and HLA markers
            aa_mask = assoc_df['SNP'].str.match(aa_pattern)
            hla_mask = assoc_df['SNP'].str.match(hla_pattern)
            
            self.aa_results_df = assoc_df.loc[aa_mask, :].copy()
            self.hla_results_df = assoc_df.loc[hla_mask, :].copy()
            
            # Validation
            if self.aa_results_df.empty:
                raise ValueError(f"No amino acid markers found for HLA-{self.hla_gene}")
            
            if self.hla_results_df.empty:
                raise ValueError(f"No HLA allele markers found for HLA-{self.hla_gene}")
            
            self._log(f"Found {len(self.aa_results_df)} AA markers and {len(self.hla_results_df)} HLA markers")
            
            return True
            
        except Exception as e:
            self._log(f"Error loading association results: {str(e)}", "ERROR")
            return False
    
    def preprocess_maptable(self) -> bool:
        """
        Preprocess maptable by filtering and matching with association data.
        Replicates HATK's preprocessing steps.
        """
        try:
            self._log("Preprocessing maptable...")
            
            # Step 1: Filter HLA alleles present in association results
            # Extract HLA alleles from HLA markers (remove HLA_ prefix)
            hla_alleles_in_assoc = self.hla_results_df['SNP'].apply(
                lambda x: re.sub(pattern=r'HLA_', repl='', string=x)
            ).unique()
            
            self._log(f"Found {len(hla_alleles_in_assoc)} HLA alleles in association results")
            
            # Filter maptable for these alleles
            allele_mask = self.maptable_df.index.to_series().isin(hla_alleles_in_assoc)
            processed_maptable = self.maptable_df.loc[allele_mask].copy()
            
            if processed_maptable.empty:
                raise ValueError("No matching HLA alleles found between maptable and association results")
            
            self._log(f"Filtered maptable to {processed_maptable.shape[0]} matching alleles")
            
            # Step 2: Filter polymorphic positions only
            polymorphic_mask = processed_maptable.apply(lambda x: len(set(x)) > 1, axis=0)
            processed_maptable = processed_maptable.loc[:, polymorphic_mask]
            
            self._log(f"Filtered to {processed_maptable.shape[1]} polymorphic positions")
            
            # Step 3: Filter positions present in association results
            maptable_positions = pd.Series([item[0] for item in processed_maptable.columns.tolist()])
            
            # Extract relative positions from association markers
            position_pattern = re.compile(f'^AA_{self.hla_gene}_(-?\\d+)_\\d+_.+')
            aa_positions = self.aa_results_df['SNP'].str.extract(position_pattern, expand=False)
            aa_positions_str = aa_positions.astype(str)
            
            # Filter maptable columns for positions in association data
            valid_position_mask = maptable_positions.isin(aa_positions_str).tolist()
            processed_maptable = processed_maptable.loc[:, valid_position_mask]
            
            if processed_maptable.empty:
                raise ValueError("No matching amino acid positions found")
            
            self._log(f"Final maptable shape: {processed_maptable.shape}")
            
            # Reindex association results with relative positions for easier processing
            aa_results_indexed = self.aa_results_df.copy()
            aa_results_indexed.index = pd.Index(aa_positions_str, name="rel_pos")
            
            self.processed_maptable = processed_maptable
            self.aa_results_indexed = aa_results_indexed
            
            return True
            
        except Exception as e:
            self._log(f"Error preprocessing maptable: {str(e)}", "ERROR")
            return False
    
    def map_pvalues_to_amino_acids(self) -> bool:
        """
        Core function to map p-values from association results to amino acid positions.
        Replicates the HATK algorithm for bi-allelic and multi-allelic markers.
        """
        try:
            self._log("Mapping p-values to amino acid positions...")

            columns = self.processed_maptable.columns.tolist()
            new_assoc_list = []
            
            for i in range(self.processed_maptable.shape[1]):
                col_info = columns[i]  # (relative_position, genomic_position, exon_type)
                rel_position = col_info[0]
                
                if self.verbose and i % 50 == 0:
                    self._log(f"Processing position {i+1}/{self.processed_maptable.shape[1]}: {rel_position}")
                
                # Get markers for this position
                try:
                    markers_at_position = self.aa_results_indexed.loc[[rel_position]]
                except KeyError:
                    # Position not found in association results
                    continue
                
                if markers_at_position.shape[0] > 0:
                    # Get amino acid sequences for this position
                    amino_acids = self.processed_maptable.iloc[:, i]
                    
                    # get only numeric columns
                    pvalues = pd.to_numeric(markers_at_position['P'], errors='coerce')
                    or_values = pd.to_numeric(markers_at_position['OR'], errors='coerce')
                    
                    # check for NaN values
                    if pvalues.isna().any() or or_values.isna().any():
                        self._log(f"WARNING: Invalid numeric values in position {rel_position}")
                        continue
                    
                    if markers_at_position.shape[0] > 1:
                        # Multi-allelic case
                        snp_names = markers_at_position['SNP']
                        
                        # Extract amino acid characters from SNP names
                        aa_chars = [snp.split('_')[-1] for snp in snp_names.tolist()]
                        
                        # Create mapping from amino acid character to p-value and OR
                        pvalues.index = pd.Index(aa_chars)
                        or_values.index = pd.Index(aa_chars)
                        
                        # Transform amino acids to signed -log10(p) values
                        def transform_aa_multi(aa_char):
                            if aa_char in pvalues.index:
                                # convert to float and use max
                                p_val = max(float(pvalues.loc[aa_char]), float(self.min_pvalue))
                                or_val = float(or_values.loc[aa_char])
                                or_sign = (2 * int(or_val > 1) - 1)
                                return -log10(p_val) * or_sign
                            else:
                                return 0  # Missing data
                        
                        transformed_aa = amino_acids.apply(transform_aa_multi)
                        
                    else:
                        # Bi-allelic case
                        ref_allele = str(markers_at_position['A1'].iloc[0])  # convert to string
                        p_val = max(float(pvalues.iloc[0]), float(self.min_pvalue))  # convert to float and use max
                        or_val = float(or_values.iloc[0])  # convert to float
                        
                        or_sign = (2 * int(or_val > 1) - 1)
                        base_value = -log10(p_val) * or_sign
                        
                        # Apply character-specific direction
                        def transform_aa_bi(aa_char):
                            char_sign = (2 * int(str(aa_char) == ref_allele) - 1)  # convert to string
                            return base_value * char_sign
                        
                        transformed_aa = amino_acids.apply(transform_aa_bi)
                    
                    # Cap extreme values for display
                    transformed_aa = transformed_aa.clip(
                        -self.max_pvalue_display, self.max_pvalue_display
                    )
                    
                    new_assoc_list.append(transformed_aa)
            
            # Combine all transformed columns
            if new_assoc_list:
                self.aa_pvalue_matrix = pd.concat(new_assoc_list, axis=1)
                
                # Set proper column and index names
                self.aa_pvalue_matrix.columns = [s.name[0] for s in new_assoc_list]
                self.aa_pvalue_matrix.index = self.processed_maptable.loc[self.aa_pvalue_matrix.index].index

                self._log(f"Generated p-value matrix: {self.aa_pvalue_matrix.shape}")
                return True
            else:
                raise ValueError("No valid associations found for mapping")
                
        except Exception as e:
            self._log(f"Error mapping p-values to amino acids: {str(e)}", "ERROR")
            return False
    
    def create_hla_allele_pvalues(self) -> bool:
        """
        Create p-value series for HLA alleles from association results.
        """
        try:
            self._log("Processing HLA allele significance...")
            
            # Get HLA alleles from processed maptable
            hla_alleles = self.processed_maptable.index.tolist()
            
            # Prepare HLA allele data
            hla_data = self.hla_results_df[['SNP', 'P', 'OR']].copy()
            
            # Create mapping from maptable alleles to association results
            hla_mapping = pd.DataFrame({
                'HLA1': hla_alleles,
                'HLA2': ['HLA_' + allele for allele in hla_alleles]
            })
            
            # Merge with association results
            merged_data = hla_mapping.merge(hla_data, left_on='HLA2', right_on='SNP', how='left')
            
            # convert P, OR columns to numeric
            merged_data['P'] = pd.to_numeric(merged_data['P'], errors='coerce')
            merged_data['OR'] = pd.to_numeric(merged_data['OR'], errors='coerce')

            # Calculate signed -log10(p) values
            def calculate_signed_log10p(row):
                if pd.isna(row['P']) or pd.isna(row['OR']):
                    return 0
                # convert to float and calculate
                p_val = max(float(row['P']), self.min_pvalue)
                or_val = float(row['OR'])
                or_sign = (2 * int(or_val > 1) - 1)
                return -log10(p_val) * or_sign
            
            allele_pvalues = merged_data.apply(calculate_signed_log10p, axis=1)
            allele_pvalues.index = merged_data['HLA1']

            # Cap extreme values
            self.hla_allele_pvalues = allele_pvalues.clip(
                -self.max_pvalue_display, self.max_pvalue_display
            )
            
            self._log(f"Generated HLA allele p-values for {len(self.hla_allele_pvalues)} alleles")
            
            return True
            
        except Exception as e:
            self._log(f"Error creating HLA allele p-values: {str(e)}", "ERROR")
            return False
    
    def save_intermediate_files(self) -> bool:
        """
        Save intermediate files compatible with HATK format.
        
        Creates three files:
        - .map.txt: Amino acid character matrix
        - .assoc.txt: Signed -log10(p) value matrix
        - .alleleP.txt: HLA allele significance values
        """
        try:
            if not self.save_intermediates:
                return True
            
            self._log("Saving intermediate files...")
            
            # Save amino acid matrix (.map.txt equivalent)
            map_path = self.output_prefix + '.map.txt'
            
            # Align matrices to ensure same structure
            aligned_maptable = self.processed_maptable.loc[
                self.aa_pvalue_matrix.index, 
                self.aa_pvalue_matrix.columns
            ]
            
            aligned_maptable.to_csv(map_path, sep='\t', header=True, index=True)
            self.intermediate_files['map'] = map_path
            self._log(f"Saved amino acid matrix: {map_path}")
            
            # Save association matrix (.assoc.txt equivalent)
            assoc_path = self.output_prefix + '.assoc.txt'
            self.aa_pvalue_matrix.to_csv(assoc_path, sep='\t', header=True, index=True)
            self.intermediate_files['assoc'] = assoc_path
            self._log(f"Saved p-value matrix: {assoc_path}")
            
            # Save HLA allele p-values (.alleleP.txt equivalent)
            allelep_path = self.output_prefix + '.alleleP.txt'
            self.hla_allele_pvalues.to_csv(allelep_path, sep='\t', header=True, index=True)
            self.intermediate_files['alleleP'] = allelep_path
            self._log(f"Saved HLA allele p-values: {allelep_path}")
            
            return True
            
        except Exception as e:
            self._log(f"Error saving intermediate files: {str(e)}", "ERROR")
            return False
    
    def create_visualization(self) -> bool:
        """
        Create heatmap visualization using plotly or matplotlib.
        """
        try:
            self._log("Creating heatmap visualization...")
            
            # Align matrices for visualization
            aligned_maptable = self.processed_maptable.loc[
                self.aa_pvalue_matrix.index, 
                self.aa_pvalue_matrix.columns
            ]
            
            if self.use_plotly:
                try:
                    self.heatmap_file = create_plotly_heatmap(
                        amino_acid_matrix=aligned_maptable,
                        aa_pvalue_matrix=self.aa_pvalue_matrix,
                        hla_allele_pvalues=self.hla_allele_pvalues,
                        output_path=self.output_prefix,
                        hla_gene=self.hla_gene,
                        max_pvalue_display=self.max_pvalue_display
                    )
                    self._log(f"Created interactive heatmap: {self.heatmap_file}")
                    
                except Exception as e:
                    self._log(f"Plotly visualization failed: {str(e)}", "WARNING")
                    self._log("Falling back to matplotlib...")
                    self.use_plotly = False
            
            if not self.use_plotly:
                self.heatmap_file = create_matplotlib_heatmap(
                    amino_acid_matrix=aligned_maptable,
                    aa_pvalue_matrix=self.aa_pvalue_matrix,
                    hla_allele_pvalues=self.hla_allele_pvalues,
                    output_path=self.output_prefix,
                    hla_gene=self.hla_gene,
                    max_pvalue_display=self.max_pvalue_display
                )
                self._log(f"Created static heatmap: {self.heatmap_file}")
            
            return True
            
        except Exception as e:
            self._log(f"Error creating visualization: {str(e)}", "ERROR")
            return False
    
    def generate(self) -> Optional[str]:
        """
        Main method to generate heatmap with intermediate files.
        
        Returns:
            Path to generated heatmap file if successful, None otherwise
        """
        try:
            start_time = time.time()
            self._log(f"Starting heatmap generation for HLA-{self.hla_gene}")
            
            # Step 1: Validate input files
            is_valid, error_msg = validate_input_files(self.maptable_file, self.assoc_file)
            if not is_valid:
                self._log(error_msg, "ERROR")
                return None
            
            # Step 2: Load data
            if not self.load_maptable():
                return None
            
            if not self.load_association_results():
                return None
            
            # Step 3: Preprocess data
            if not self.preprocess_maptable():
                return None
            
            # Step 4: Map p-values to amino acids
            if not self.map_pvalues_to_amino_acids():
                return None
            
            # Step 5: Create HLA allele p-values
            if not self.create_hla_allele_pvalues():
                return None
            
            # Step 6: Save intermediate files
            if not self.save_intermediate_files():
                return None
            
            # Step 7: Create visualization
            if not self.create_visualization():
                return None
            
            # Success
            elapsed_time = time.time() - start_time
            self._log(f"Heatmap generation completed in {elapsed_time:.2f} seconds")
            
            self.success = True
            return self.heatmap_file
            
        except Exception as e:
            self._log(f"Heatmap generation failed: {str(e)}", "ERROR")
            return None
    
    def get_results(self) -> Dict[str, Any]:
        """
        Get comprehensive results including all generated files and statistics.
        """
        results = {
            'success': self.success,
            'heatmap_file': self.heatmap_file,
            'intermediate_files': self.intermediate_files,
            'hla_gene': self.hla_gene,
            'statistics': {}
        }
        
        if self.success:
            results['statistics'] = {
                'maptable_shape': self.processed_maptable.shape if self.processed_maptable is not None else None,
                'aa_markers_count': len(self.aa_results_df) if self.aa_results_df is not None else 0,
                'hla_markers_count': len(self.hla_results_df) if self.hla_results_df is not None else 0,
                'pvalue_matrix_shape': self.aa_pvalue_matrix.shape if self.aa_pvalue_matrix is not None else None,
                'hla_alleles_count': len(self.hla_allele_pvalues) if self.hla_allele_pvalues is not None else 0
            }
        
        return results


def main():
    """
    Main function for standalone execution and testing.
    """
    print("HLA Heatmap Generator v2")
    print("This module should be imported and used through the runner script.")
    print("For standalone testing, modify the paths below:")
    
    # Example usage (modify paths as needed)
    example_config = {
        '_data_processing': {
            'significance_threshold': 0.05,
            'max_pvalue_display': 15,
            'min_pvalue': 1e-300
        }
    }
    
    # Uncomment and modify for testing
    # generator = HeatmapGenerator(
    #     assoc_file="path/to/association.assoc.logistic",
    #     maptable_file="path/to/HLA_MAPTABLE_A.hg18.imgt3320.txt",
    #     hla_gene="A",
    #     output_prefix="test_output/heatmap_A",
    #     config=example_config
    # )
    # 
    # result = generator.generate()
    # if result:
    #     print(f"Test successful: {result}")
    # else:
    #     print("Test failed")


if __name__ == "__main__":
    main()
