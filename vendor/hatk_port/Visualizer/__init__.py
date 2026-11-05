"""
HATK Visualizer Module
======================

This module provides visualization tools for HATK analysis results,
including Manhattan plots for GWAS data visualization.
"""

from .visualizer_utils import (
    categorize_marker,
    prepare_logistic_data,
    prepare_omnibus_data,
    calculate_genomic_positions,
    get_significance_thresholds,
    format_hover_text,
    filter_top_signals
)

from .manhattanPlot import ManhattanPlotter

__all__ = [
    'categorize_marker',
    'prepare_logistic_data',
    'prepare_omnibus_data',
    'calculate_genomic_positions',
    'get_significance_thresholds',
    'format_hover_text',
    'filter_top_signals',
    'ManhattanPlotter'
]

__version__ = '1.0.0'