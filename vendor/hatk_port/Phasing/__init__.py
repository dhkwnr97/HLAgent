#-*- coding: utf-8 -*-

"""
HATK Phasing Module

Comprehensive haplotype phasing pipeline with two-stage architecture:
Stage 1: Input Format Conversion (PLINK/VCF/BEAGLE -> BEAGLE)
Stage 2: BEAGLE Phasing with GCtrick workflow

Classes:
- HATK_Phasing: Main phasing pipeline class
- InputFormatConverter: Stage 1 input format conversion
- BEAGLEPhasingEngine: Stage 2 BEAGLE phasing with GCtrick

Supports multiple input formats and BEAGLE versions for maximum flexibility.
"""

from .__main__ import HATK_Phasing

# Backward compatibility - expose the main class
__all__ = ['HATK_Phasing']