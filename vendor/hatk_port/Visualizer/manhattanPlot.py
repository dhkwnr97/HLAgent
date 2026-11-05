#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
manhattanPlot.py
================
Manhattan plot visualization for HLAgent HATK pipeline.

This script generates interactive Manhattan plots for both logistic regression and 
omnibus test results using Plotly, with comprehensive support for HLA-specific analysis.

Usage:
    python manhattanPlot.py --input <input_file> --output <output_dir> --type <regression|omnibus> [options]

Examples:
    # Logistic regression plot
    python manhattanPlot.py -i data.assoc.logistic -o results/ -t regression
    
    # Omnibus test plot with filtering
    python manhattanPlot.py -i data.omnibus -o results/ -t omnibus --filter-threshold 0.01

Author: HLAgent Development Team
Date: 2025
"""

import argparse
import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
import logging
from datetime import datetime
import json

# Add project root to path for imports
project_root = str(Path(__file__).parents[4])
if project_root not in sys.path:
    sys.path.append(project_root)

# Import utility functions
from hatk_port.Visualizer.visualizer_utils import (
    prepare_logistic_data,
    prepare_omnibus_data, 
    calculate_genomic_positions,
    get_significance_thresholds,
    format_hover_text,
    filter_top_signals,
    optimize_data_for_plotting,
    generate_plot_summary,
    MARKER_COLORS
)

# Set up logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_hla_exon_data():
    """
    Load HLA exon positions and start codon data.
    
    Returns:
        tuple: (exon_df, startcodon_df) containing exon and start codon information
    """
    try:
        # Load exon positions
        exon_file = Path(__file__).parent.parent / "IMGT2Seq" / "data_for_imgt2seq" / "HLA_EXON_POSITIONS_SNPS_hg18.txt"
        exon_df = pd.read_csv(exon_file, sep='\t', header=None, 
                             names=['gene', 'start', 'end', 'strand'])
        
        # Load start codon positions
        startcodon_file = Path(__file__).parent.parent / "IMGT2Seq" / "data_for_imgt2seq" / "HLA_EXON1_START_CODON_POSITIONS_hg18.txt"
        startcodon_df = pd.read_csv(startcodon_file, sep='\t', header=None,
                                   names=['gene', 'strand', 'bp'])
        
        # Convert bp to numeric, handling 'NA' values
        startcodon_df['bp'] = pd.to_numeric(startcodon_df['bp'], errors='coerce')
        
        logger.info(f"Loaded {len(exon_df)} exon regions and {len(startcodon_df)} start codon positions")
        return exon_df, startcodon_df
        
    except FileNotFoundError as e:
        logger.warning(f"Could not load HLA annotation files: {e}")
        return pd.DataFrame(), pd.DataFrame()
    except Exception as e:
        logger.warning(f"Error loading HLA annotation data: {e}")
        return pd.DataFrame(), pd.DataFrame()


def convert_types_for_json(obj):
    """
    Recursively convert numpy types to native Python types for JSON serialization.
    """
    if isinstance(obj, (np.int64, np.int32, np.int16, np.int8)):
        return int(obj)
    if isinstance(obj, (np.float64, np.float32, np.float16)):
        return float(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if isinstance(obj, dict):
        return {k: convert_types_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [convert_types_for_json(i) for i in obj]
    return obj


class ManhattanPlotter:
    """
    Manhattan plotter with comprehensive visualization capabilities.
    """
    
    def __init__(self, plot_type: str = 'regression', interactive: bool = True, 
                 hla_region_only: bool = False):
        """
        Initialize the Manhattan plotter.
        
        Args:
            plot_type: Type of plot ('regression' or 'omnibus')
            interactive: Whether to create interactive plots
            hla_region_only: Whether to focus on HLA region (chr6:29-34Mb) with exon annotations
        """
        self.plot_type = plot_type
        self.interactive = interactive
        self.hla_region_only = hla_region_only
        self.thresholds = get_significance_thresholds()
        self.colors = MARKER_COLORS
        
        # Load HLA annotation data if needed
        self.exon_df, self.startcodon_df = load_hla_exon_data() if hla_region_only else (pd.DataFrame(), pd.DataFrame())
        
        logger.info(f"Initialized {self.__class__.__name__} for {plot_type} plots")
        if hla_region_only:
            logger.info("HLA region focus enabled with exon annotations")
    
    def create_regression_plot(self, data: pd.DataFrame, title: str = None) -> go.Figure:
        """
        Create Manhattan plot for logistic regression results.
        
        Args:
            data: Prepared DataFrame from prepare_logistic_data
            title: Custom plot title
            
        Returns:
            Plotly figure object
        """
        if title is None:
            title = "Manhattan Plot - Logistic Regression Results"
        
        logger.info(f"Creating regression plot with {len(data)} markers")
        
        if self.hla_region_only:
            return self._create_hla_regression_plot(data, title)
        else:
            return self._create_standard_regression_plot(data, title)
    
    def _create_standard_regression_plot(self, data: pd.DataFrame, title: str) -> go.Figure:
        """Create standard regression plot without HLA annotations."""
        # Calculate cumulative positions
        data, chr_positions = calculate_genomic_positions(data)
        
        # Create figure
        fig = go.Figure()
        
        # Plot points by category with styling
        for category in sorted(data['category'].unique()):
            category_data = data[data['category'] == category]
            
            if len(category_data) == 0:
                continue
                
            # Create hover text
            hover_text = category_data.apply(
                lambda row: format_hover_text(row, 'regression'), axis=1
            )
            
            # Determine marker size based on significance
            marker_sizes = np.where(
                category_data['-log10P'] > self.thresholds['genome_wide'], 10,
                np.where(category_data['-log10P'] > self.thresholds['suggestive'], 8, 6)
            )
            
            fig.add_trace(go.Scatter(
                x=category_data['pos_cum'],
                y=category_data['-log10P'],
                mode='markers',
                marker=dict(
                    size=marker_sizes,
                    color=category_data['color'].iloc[0],
                    opacity=0.7,
                    line=dict(width=0.5, color='rgba(0,0,0,0.2)')
                ),
                name=f"{category} (n={len(category_data)})",
                text=hover_text,
                hovertemplate='%{text}<extra></extra>',
                legendgroup=category
            ))
        
        # Add significance lines with styling
        self._add_significance_lines(fig, max_y=data['-log10P'].max())
        
        # Configure x-axis with chromosome labels
        self._configure_regression_axes(fig, data, chr_positions, title)
        
        # Add annotations for top signals
        self._annotate_top_signals(fig, data, top_n=5)
        
        logger.info("Standard regression plot created successfully")
        return fig
    
    def _create_hla_regression_plot(self, data: pd.DataFrame, title: str) -> go.Figure:
        """Create HLA-focused regression plot with exon annotations."""
        # Filter data to HLA region (chr6:28.8-34.2Mb) - extended range for better visibility
        hla_data = data[(data['CHR'] == 6) & (data['BP'] >= 28.8e6) & (data['BP'] <= 34.2e6)].copy()
        
        if len(hla_data) == 0:
            logger.warning("No data found in HLA region (chr6:28.8-34.2Mb)")
            return self._create_standard_regression_plot(data, title)
        
        logger.info(f"Creating HLA-focused plot with {len(hla_data)} markers")
        
        # Create subplot with exon annotations
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.88, 0.12],
            vertical_spacing=0.02,
            subplot_titles=(title, "HLA Gene Structure")
        )
        
        # Plot Manhattan data in upper subplot
        for category in sorted(hla_data['category'].unique()):
            category_data = hla_data[hla_data['category'] == category]
            
            if len(category_data) == 0:
                continue
                
            # Create hover text
            hover_text = category_data.apply(
                lambda row: format_hover_text(row, 'regression'), axis=1
            )
            
            # Determine marker size based on significance
            marker_sizes = np.where(
                category_data['-log10P'] > self.thresholds['genome_wide'], 10,
                np.where(category_data['-log10P'] > self.thresholds['suggestive'], 8, 6)
            )
            
            fig.add_trace(go.Scatter(
                x=category_data['BP'],
                y=category_data['-log10P'],
                mode='markers',
                marker=dict(
                    size=marker_sizes,
                    color=category_data['color'].iloc[0],
                    opacity=0.7,
                    line=dict(width=0.5, color='rgba(0,0,0,0.2)')
                ),
                name=f"{category} (n={len(category_data)})",
                text=hover_text,
                hovertemplate='%{text}<extra></extra>',
                legendgroup=category,
                showlegend=True
            ), row=1, col=1)
        
        # Add significance lines
        self._add_hla_significance_lines(fig, max_y=hla_data['-log10P'].max())
        
        # Add exon annotations in lower subplot
        if not self.exon_df.empty:
            for _, row in self.exon_df.iterrows():
                fig.add_trace(go.Bar(
                    x=[(row['start'] + row['end']) / 2],
                    y=[-0.2],
                    width=[row['end'] - row['start']],
                    marker=dict(
                        color="LightSeaGreen" if row['strand'] == "+" else "LightSlateGray",
                        opacity=0.8
                    ),
                    name=row['gene'],
                    hovertemplate=f"{row['gene']}: {row['start']:,}–{row['end']:,}<br>Strand: {row['strand']}<extra></extra>",
                    showlegend=False
                ), row=2, col=1)
        
        # Add start codon annotations
        if not self.startcodon_df.empty:
            valid_startcodon = self.startcodon_df.dropna(subset=['bp'])
            if len(valid_startcodon) > 0:
                # Calculate text positions to avoid overlap
                text_positions = self._calculate_text_positions(valid_startcodon['bp'].values)
                
                fig.add_trace(go.Scatter(
                    x=valid_startcodon['bp'],
                    y=[-0.1] * len(valid_startcodon),
                    mode='markers+text',
                    text=valid_startcodon['gene'],
                    textposition=text_positions,
                    marker=dict(
                        symbol="triangle-up",
                        size=8,
                        color=['red' if s == "+" else 'blue' for s in valid_startcodon['strand']]
                    ),
                    name="Start Codon",
                    hovertemplate='%{text}<br>Position: %{x:,}<br>Strand: %{marker.color}<extra></extra>',
                    showlegend=False
                ), row=2, col=1)
        
        # Configure axes
        self._configure_hla_axes(fig, hla_data, title)
        
        # Hide y-axis for exon subplot
        fig.update_yaxes(visible=False, row=2, col=1)
        
        # Add strand color legend
        self._add_strand_legend(fig)
        
        logger.info("HLA-focused regression plot created successfully")
        return fig
    
    def create_omnibus_plot(self, data: pd.DataFrame, title: str = None) -> go.Figure:
        """
        Create Manhattan plot for omnibus test results.
        
        Args:
            data: Prepared DataFrame from prepare_omnibus_data
            title: Custom plot title
            
        Returns:
            Plotly figure object
        """
        if title is None:
            title = "Manhattan Plot - Omnibus Test Results"
        
        logger.info(f"Creating omnibus plot with {len(data)} variants")
        
        if self.hla_region_only:
            return self._create_hla_omnibus_plot(data, title)
        else:
            return self._create_standard_omnibus_plot(data, title)
    
    def _create_standard_omnibus_plot(self, data: pd.DataFrame, title: str) -> go.Figure:
        """Create standard omnibus plot without HLA annotations."""
        # Sort data by position for better visualization
        data = data.sort_values('position')
        
        # Create figure
        fig = go.Figure()
        
        # Plot points by category with styling
        for category in sorted(data['category'].unique()):
            category_data = data[data['category'] == category]
            
            if len(category_data) == 0:
                continue
            
            # Create hover text
            hover_text = category_data.apply(
                lambda row: format_hover_text(row, 'omnibus'), axis=1
            )
            
            # Determine marker size based on significance
            marker_sizes = np.where(
                category_data['-log10P'] > self.thresholds['genome_wide'], 12,
                np.where(category_data['-log10P'] > self.thresholds['suggestive'], 10, 8)
            )
            
            fig.add_trace(go.Scatter(
                x=category_data['position'],
                y=category_data['-log10P'],
                mode='markers',
                marker=dict(
                    size=marker_sizes,
                    color=category_data['color'].iloc[0],
                    opacity=0.8,
                    line=dict(width=0.8, color='rgba(0,0,0,0.3)')
                ),
                name=f"{category} (n={len(category_data)})",
                text=hover_text,
                hovertemplate='%{text}<extra></extra>',
                legendgroup=category
            ))
        
        # Add significance lines
        self._add_significance_lines(fig, max_y=data['-log10P'].max())
        
        # Configure axes
        self._configure_omnibus_axes(fig, data, title)
        
        # Add annotations for top signals
        self._annotate_top_signals(fig, data, top_n=5, position_col='position')
        
        logger.info("Standard omnibus plot created successfully")
        return fig
    
    def _create_hla_omnibus_plot(self, data: pd.DataFrame, title: str) -> go.Figure:
        """Create HLA-focused omnibus plot with exon annotations."""
        # Filter data to HLA region (28.8-34.2Mb) - extended range for better visibility
        hla_data = data[(data['position'] >= 28.8e6) & (data['position'] <= 34.2e6)].copy()
        
        if len(hla_data) == 0:
            logger.warning("No data found in HLA region (28.8-34.2Mb)")
            return self._create_standard_omnibus_plot(data, title)
        
        logger.info(f"Creating HLA-focused omnibus plot with {len(hla_data)} variants")
        
        # Create subplot with exon annotations
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            row_heights=[0.75, 0.25],
            vertical_spacing=0.02,
            subplot_titles=(title, "HLA Gene Structure")
        )
        
        # Plot omnibus data in upper subplot
        for category in sorted(hla_data['category'].unique()):
            category_data = hla_data[hla_data['category'] == category]
            
            if len(category_data) == 0:
                continue
            
            # Create hover text
            hover_text = category_data.apply(
                lambda row: format_hover_text(row, 'omnibus'), axis=1
            )
            
            # Determine marker size based on significance
            marker_sizes = np.where(
                category_data['-log10P'] > self.thresholds['genome_wide'], 12,
                np.where(category_data['-log10P'] > self.thresholds['suggestive'], 10, 8)
            )
            
            fig.add_trace(go.Scatter(
                x=category_data['position'],
                y=category_data['-log10P'],
                mode='markers',
                marker=dict(
                    size=marker_sizes,
                    color=category_data['color'].iloc[0],
                    opacity=0.8,
                    line=dict(width=0.8, color='rgba(0,0,0,0.3)')
                ),
                name=f"{category} (n={len(category_data)})",
                text=hover_text,
                hovertemplate='%{text}<extra></extra>',
                legendgroup=category,
                showlegend=True
            ), row=1, col=1)
        
        # Add significance lines
        self._add_hla_significance_lines(fig, max_y=hla_data['-log10P'].max())
        
        # Add exon annotations in lower subplot
        if not self.exon_df.empty:
            for _, row in self.exon_df.iterrows():
                fig.add_trace(go.Bar(
                    x=[(row['start'] + row['end']) / 2],
                    y=[0.05],
                    width=[row['end'] - row['start']],
                    marker=dict(
                        color="LightSeaGreen" if row['strand'] == "+" else "LightSlateGray",
                        opacity=0.8
                    ),
                    name=row['gene'],
                    hovertemplate=f"{row['gene']}: {row['start']:,}–{row['end']:,}<br>Strand: {row['strand']}<extra></extra>",
                    showlegend=False
                ), row=2, col=1)
        
        # Add start codon annotations
        if not self.startcodon_df.empty:
            valid_startcodon = self.startcodon_df.dropna(subset=['bp'])
            if len(valid_startcodon) > 0:
                # Calculate text positions to avoid overlap
                text_positions = self._calculate_text_positions(valid_startcodon['bp'].values)
                
                fig.add_trace(go.Scatter(
                    x=valid_startcodon['bp'],
                    y=[0.01] * len(valid_startcodon),
                    mode='markers+text',
                    text=valid_startcodon['gene'],
                    textposition=text_positions,
                    marker=dict(
                        symbol="triangle-up",
                        size=8,
                        color=['red' if s == "+" else 'blue' for s in valid_startcodon['strand']]
                    ),
                    name="Start Codon",
                    hovertemplate='%{text}<br>Position: %{x:,}<br>Strand: %{marker.color}<extra></extra>',
                    showlegend=False
                ), row=2, col=1)
        
        # Configure axes
        self._configure_hla_axes(fig, hla_data, title)
        
        # Hide y-axis for exon subplot
        fig.update_yaxes(visible=False, row=2, col=1)
        
        # Add strand color legend
        self._add_strand_legend(fig)
        
        logger.info("HLA-focused omnibus plot created successfully")
        return fig
    
    def _calculate_text_positions(self, positions):
        """
        Calculate text positions to alternate between top and bottom for gene labels.
        
        Args:
            positions: Array of genomic positions
            
        Returns:
            List of text position strings
        """
        if len(positions) <= 1:
            return ["top center"] * len(positions)
        
        # Sort positions and assign alternating positions
        sorted_indices = np.argsort(positions)
        text_positions = ["top center"] * len(positions)
        
        for i in range(1, len(sorted_indices)):
            # Alternate between top and bottom
            if text_positions[sorted_indices[i-1]] == "top center":
                text_positions[sorted_indices[i]] = "bottom center"
            else:
                text_positions[sorted_indices[i]] = "top center"
        
        return text_positions
    
    def _add_strand_legend(self, fig):
        """Add a simple legend explaining strand colors."""
        fig.add_annotation(
            x=0.02,
            y=0.98,
            xref="paper",
            yref="paper",
            text="<b>Strand Colors:</b><br>Red = + strand<br>Blue = - strand",
            showarrow=False,
            bgcolor="rgba(255,255,255,0.8)",
            bordercolor="black",
            borderwidth=1,
            font=dict(size=10)
        )

    def _add_significance_lines(self, fig: go.Figure, max_y: float):
        """Add significance threshold lines to the plot."""
        # Genome-wide significance line
        fig.add_hline(
            y=self.thresholds['genome_wide'],
            line_dash="solid",
            line_color="red",
            line_width=2,
            annotation_text="Genome-wide (p=5×10⁻⁸)",
            annotation_position="top right"
        )
        
        # Suggestive significance line
        fig.add_hline(
            y=self.thresholds['suggestive'],
            line_dash="dash",
            line_color="orange",
            line_width=1.5,
            annotation_text="Suggestive (p=1×10⁻⁵)",
            annotation_position="top right"
        )
        
        # Add nominal significance if max_y is low enough
        if max_y < 10:
            fig.add_hline(
                y=self.thresholds['nominal'],
                line_dash="dot",
                line_color="gray",
                line_width=1,
                annotation_text="Nominal (p=0.05)",
                annotation_position="top right"
            )
    
    def _add_hla_significance_lines(self, fig: go.Figure, max_y: float):
        """Add significance threshold lines to HLA plots."""
        # Genome-wide significance line
        fig.add_hline(
            y=self.thresholds['genome_wide'],
            line_dash="solid",
            line_color="red",
            line_width=2,
            annotation_text="Genome-wide (p=5×10⁻⁸)",
            annotation_position="top right",
            row=1, col=1
        )
        
        # Suggestive significance line
        fig.add_hline(
            y=self.thresholds['suggestive'],
            line_dash="dash",
            line_color="orange",
            line_width=1.5,
            annotation_text="Suggestive (p=1×10⁻⁵)",
            annotation_position="top right",
            row=1, col=1
        )
        
        # Add nominal significance if max_y is low enough
        if max_y < 10:
            fig.add_hline(
                y=self.thresholds['nominal'],
                line_dash="dot",
                line_color="gray",
                line_width=1,
                annotation_text="Nominal (p=0.05)",
                annotation_position="top right",
                row=1, col=1
            )
    
    def _configure_regression_axes(self, fig: go.Figure, data: pd.DataFrame, 
                                 chr_positions: dict, title: str):
        """Configure axes for regression plots."""
        # Calculate chromosome centers for x-axis labels
        chr_labels = sorted(data['CHR'].unique())
        chr_centers = []
        
        for chr_num in chr_labels:
            chr_data = data[data['CHR'] == chr_num]
            center = (chr_positions[chr_num] + chr_data['pos_cum'].max()) / 2
            chr_centers.append(center)
        
        # Update layout with styling
        fig.update_layout(
            title=dict(
                text=title,
                x=0.5,
                font=dict(size=18, family="Arial, sans-serif")
            ),
            xaxis=dict(
                title=dict(
                    text="Chromosome",
                    font=dict(size=14)
                ),
                tickmode='array',
                tickvals=chr_centers,
                ticktext=[f"Chr {chr}" for chr in chr_labels],
                gridcolor='lightgray',
                gridwidth=1,
                showgrid=True,
                zeroline=False
            ),
            yaxis=dict(
                title=dict(
                    text="-log₁₀(P-value)",
                    font=dict(size=14)
                ),
                gridcolor='lightgray',
                gridwidth=1,
                showgrid=True,
                zeroline=False
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='closest',
            height=700,
            width=1600,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=12)
            ),
            margin=dict(l=80, r=80, t=100, b=80)
        )
    
    def _configure_omnibus_axes(self, fig: go.Figure, data: pd.DataFrame, title: str):
        """Configure axes for omnibus plots."""
        fig.update_layout(
            title=dict(
                text=title,
                x=0.5,
                font=dict(size=18, family="Arial, sans-serif")
            ),
            xaxis=dict(
                title=dict(
                    text="Genomic Position / Amino Acid Position",
                    font=dict(size=14)
                ),
                gridcolor='lightgray',
                gridwidth=1,
                showgrid=True,
                zeroline=False
            ),
            yaxis=dict(
                title=dict(
                    text="-log₁₀(P-value)",
                    font=dict(size=14)
                ),
                gridcolor='lightgray',
                gridwidth=1,
                showgrid=True,
                zeroline=False
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='closest',
            height=700,
            width=1400,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=12)
            ),
            margin=dict(l=80, r=80, t=100, b=80)
        )
    
    def _configure_hla_axes(self, fig: go.Figure, data: pd.DataFrame, title: str):
        """Configure axes for HLA-focused plots."""
        # Set x-axis range to HLA region (28.8-34.2 Mb) - extended for better visibility
        fig.update_xaxes(
            range=[28.8e6, 34.2e6],
            title="Chromosome 6 position (bp)",
            gridcolor='lightgray',
            gridwidth=1,
            showgrid=True,
            zeroline=False,
            row=1, col=1
        )
        
        # Set y-axis for main plot
        fig.update_yaxes(
            title="-log₁₀(P-value)",
            gridcolor='lightgray',
            gridwidth=1,
            showgrid=True,
            zeroline=False,
            row=1, col=1
        )
        
        # Set x-axis for exon subplot
        fig.update_xaxes(
            range=[28.8e6, 34.2e6],
            title="Chromosome 6 position (bp)",
            gridcolor='lightgray',
            gridwidth=1,
            showgrid=True,
            zeroline=False,
            row=2, col=1
        )
        
        # Update overall layout
        fig.update_layout(
            title=dict(
                text=title,
                x=0.5,
                font=dict(size=18, family="Arial, sans-serif")
            ),
            plot_bgcolor='white',
            paper_bgcolor='white',
            hovermode='closest',
            height=800,
            width=1400,
            showlegend=True,
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1,
                font=dict(size=12)
            ),
            margin=dict(l=80, r=80, t=100, b=80)
        )
        
        # Add custom x-axis ticks for HLA region
        ticks = [28e6, 29e6, 30e6, 31e6, 32e6, 33e6, 34e6]
        labels = [f"{t/1e6:.1f} Mb" if t in [28.8e6, 34.2e6] else f"{t/1e6:.0f} Mb" for t in ticks]
        
        fig.update_xaxes(
            tickvals=ticks,
            ticktext=labels,
            row=1, col=1
        )
        
        fig.update_xaxes(
            tickvals=ticks,
            ticktext=labels,
            row=2, col=1
        )
    
    def _annotate_top_signals(self, fig: go.Figure, data: pd.DataFrame, 
                            top_n: int = 5, position_col: str = 'pos_cum'):
        """Add annotations for top signals."""
        try:
            # Get top signals
            top_signals = data.nlargest(top_n, '-log10P')
            
            for _, signal in top_signals.iterrows():
                if signal['-log10P'] > self.thresholds['suggestive']:
                    # Get marker name
                    marker_name = signal.get('SNP', signal.get('Variant', 'Unknown'))
                    
                    # Truncate long names
                    if len(marker_name) > 20:
                        marker_name = marker_name[:17] + "..."
                    
                    fig.add_annotation(
                        x=signal[position_col],
                        y=signal['-log10P'],
                        text=marker_name,
                        showarrow=True,
                        arrowhead=2,
                        arrowsize=1,
                        arrowwidth=1,
                        arrowcolor="black",
                        ax=20,
                        ay=-30,
                        font=dict(size=10),
                        bgcolor="rgba(255,255,255,0.8)",
                        bordercolor="black",
                        borderwidth=1
                    )
        except Exception as e:
            logger.warning(f"Could not add annotations: {str(e)}")

def save_plot_with_metadata(fig: go.Figure, output_path: str, 
                          summary: dict, args: argparse.Namespace):
    """Save plot with comprehensive metadata."""
    try:
        # Save the main plot
        fig.write_html(output_path, include_plotlyjs='cdn')
        
        # Save metadata
        metadata = {
            'generated_at': datetime.now().isoformat(),
            'script_version': '2.0.0',
            'input_file': args.input,
            'plot_type': args.type,
            'arguments': vars(args),
            'data_summary': summary
        }
        
        # Convert numpy types for JSON serialization
        metadata = convert_types_for_json(metadata)
        
        metadata_path = output_path.replace('.html', '_metadata.json')
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        logger.info(f"Plot saved with metadata: {output_path}")
        
    except Exception as e:
        logger.error(f"Error saving plot: {str(e)}")
        raise

def run_plot_generation(args: argparse.Namespace):
    """
    Runs the Manhattan plot generation process based on provided arguments.

    Args:
        args (argparse.Namespace): Arguments for plot generation.
                                   Expected attributes: verbose, input, output,
                                   type, hla_region, title, format.
    """
    # Set up logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    start_time = datetime.now()
    
    # Validate input file
    if not os.path.exists(args.input):
        raise FileNotFoundError(f"Input file not found: {args.input}")
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output, exist_ok=True)
    
    # Load and prepare data
    logger.info(f"Loading data from {args.input}")
    
    if args.type == 'regression':
        data = prepare_logistic_data(args.input)
        title = args.title or "Manhattan Plot - Logistic Regression Results"
        
        # Initialize plotter with HLA region option
        plotter = ManhattanPlotter(plot_type='regression', hla_region_only=args.hla_region)
        fig = plotter.create_regression_plot(data, title=title)
        
    elif args.type == 'omnibus':
        data = prepare_omnibus_data(args.input)
        title = args.title or "Manhattan Plot - Omnibus Test Results"
        
        # Initialize plotter with HLA region option
        plotter = ManhattanPlotter(plot_type='omnibus', hla_region_only=args.hla_region)
        fig = plotter.create_omnibus_plot(data, title=title)
    
    # Generate plot summary
    summary = generate_plot_summary(data, args.type)
    
    # Generate output filename
    input_basename = os.path.splitext(os.path.basename(args.input))[0]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Add HLA indicator to filename if HLA region is focused
    hla_suffix = "_hla" if args.hla_region else ""
    
    # Save plot for each specified format
    for plot_format in args.format:
        output_filename = f"{input_basename}_manhattan{hla_suffix}_{timestamp}.{plot_format}"
        output_path = os.path.join(args.output, output_filename)
        
        if plot_format == 'html':
            save_plot_with_metadata(fig, output_path, summary, args)
            logger.info(f"Interactive HTML plot saved to {output_path}")
            
            # Also save a static preview for HTML outputs
            preview_filename = f"{input_basename}_manhattan{hla_suffix}_{timestamp}_preview.png"
            preview_path = os.path.join(args.output, preview_filename)
            try:
                fig.write_image(preview_path, width=1400, height=600, scale=1.5)
                logger.info(f"Static preview saved to {preview_path}")
            except Exception as e:
                logger.warning(f"Could not save preview image: {str(e)}")
        
        elif plot_format in ['png', 'pdf', 'svg']:
            try:
                scale = 2 if plot_format == 'png' else 1
                fig.write_image(output_path, scale=scale)
                logger.info(f"{plot_format.upper()} plot saved to {output_path}")
            except Exception as e:
                logger.error(f"Failed to save {plot_format.upper()} plot: {e}")
    
    # Print summary statistics
    processing_time = datetime.now() - start_time
    logger.info(f"Plot generation completed in {processing_time.total_seconds():.2f} seconds")
    logger.info(f"Data summary: {summary['total_markers']} markers, "
                f"max -log10(P): {summary['max_log10p']:.2f}")
    
    # Print marker type distribution
    logger.info("Marker type distribution:")
    for marker_type, count in summary['marker_types'].items():
        logger.info(f"  {marker_type}: {count}")
    
    # Print significance counts
    if 'significant_markers' in summary:
        sig_counts = summary['significant_markers']
        logger.info(f"Significant markers - Genome-wide: {sig_counts['genome_wide']}, "
                    f"Suggestive: {sig_counts['suggestive']}, "
                    f"Nominal: {sig_counts['nominal']}")
    elif 'significant_variants' in summary:
        sig_counts = summary['significant_variants']
        logger.info(f"Significant variants - Genome-wide: {sig_counts['genome_wide']}, "
                    f"Suggestive: {sig_counts['suggestive']}, "
                    f"Nominal: {sig_counts['nominal']}")
    
    # Print HLA region info if applicable
    if args.hla_region:
        logger.info("HLA region focus enabled - plot shows chr6:29-34Mb with exon annotations")


def main():
    """
    main function with comprehensive argument parsing and error handling.
    """
    parser = argparse.ArgumentParser(
        description="Generate Manhattan plots for HATK analysis results",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Standard regression plot
    python manhattanPlot.py -i data.assoc.logistic -o results/ -t regression
    
    # HLA region focused plot with exon annotations
    python manhattanPlot.py -i data.assoc.logistic -o results/ -t regression --hla-region
    
    # Omnibus test plot
    python manhattanPlot.py -i data.omnibus -o results/ -t omnibus
    
    # HLA region focused omnibus plot
    python manhattanPlot.py -i data.omnibus -o results/ -t omnibus --hla-region
        """
    )
    
    # Required arguments
    parser.add_argument('-i', '--input', required=True,
                       help='Input file path (.assoc.logistic or .omnibus)')
    parser.add_argument('-o', '--output', required=True,
                       help='Output directory path')
    parser.add_argument('-t', '--type', required=True, choices=['regression', 'omnibus'],
                       help='Type of analysis (regression or omnibus)')
    
    # Optional arguments
    parser.add_argument('--format', nargs='+', choices=['html', 'png', 'pdf', 'svg'], default=['html'],
                       help='Output format (default: html). Can specify multiple.')
    parser.add_argument('--title', help='Custom plot title')
    parser.add_argument('--hla-region', action='store_true',
                       help='Focus on HLA region (chr6:29-34Mb) with exon annotations')
    parser.add_argument('--verbose', action='store_true',
                       help='Enable verbose logging')
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    start_time = datetime.now()
    
    try:
        run_plot_generation(args)
        logger.info("Manhattan plot generation completed successfully!")
        
    except Exception as e:
        logger.error(f"Error generating Manhattan plot: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
