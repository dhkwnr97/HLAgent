#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
MetaAnalysis Module for HATK
============================

This module provides functionality for performing meta-analysis on HLA association
test results using the inverse-variance weighting method.

Main components:
- metaanal_utils: Core utility functions for meta-analysis
- MetaAnalysisError: Custom exception class
- run_meta_analysis: Main function to perform meta-analysis

Author: HLAgent Development Team
Date: 2025
"""

from .metaanal_utils import (
    MetaAnalysisError,
    read_logistic_result,
    read_marker_file,
    flip_alleles,
    inverse_variance_meta_analysis,
    run_meta_analysis,
    COMPLEMENT_BASE
)

__all__ = [
    'MetaAnalysisError',
    'read_logistic_result',
    'read_marker_file',
    'flip_alleles',
    'inverse_variance_meta_analysis',
    'run_meta_analysis',
    'COMPLEMENT_BASE'
]

__version__ = '1.0.0'
