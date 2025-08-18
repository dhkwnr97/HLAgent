#!/usr/bin/env python3
"""
HLAgent HATK (HLA Analysis Toolkit)
===================================

HLA Analysis Toolkit for HLAgent - A comprehensive suite for HLA fine-mapping
and association analysis based on the original HATK pipeline.

This toolkit provides a complete workflow for HLA analysis:

1. **IMGT2Seq**: Convert IPD-IMGT/HLA database to sequence dictionaries
2. **HLA2HPED**: Convert HLA typing results to HPED format  
3. **NomenCleaner**: Clean and standardize HLA nomenclature
4. **bMarkerGenerator**: Generate binary markers for association testing
5. **Analyzer**: Perform association tests and generate visualizations
6. **StepwiseRegression**: Stepwise conditional regression analysis
7. **OmnibusTest**: Omnibus tests with CookHLA integration
8. **MetaAnalysis**: Meta-analysis across multiple traits

Features:
- A2A Protocol support for inter-agent communication
- MCP Server integration for enhanced functionality
- Conversational interface with user approval steps
- Multiprocessing support for performance
- Comprehensive validation and error handling

Author: HLAgent Development Team
Version: 1.0.0
License: Academic Use Only
"""

# Module metadata
__version__ = "1.0.0"
__author__ = "HLAgent Development Team"
__license__ = "Academic Use Only"

# Export main modules and classes
__all__ = [
    # Modules
    'Imgt2Seq',
    'Hla2Hped',
    'NomenCleaner', 
    'BmarkerGenerator',
    'Analyzer',
    'StepwiseRegression',
    'OmnibusTest',
    'MetaAnalysis',
    
    # Main classes (implemented)
    'HLAgentIMGT2Seq',
    'IMGT2SeqConfig',
    'IMGT2SeqOutput',
    
    # Utility functions
    'create_default_imgt2seq_config',
    'get_hatk_info',
    'list_available_modules'
]

# Workflow constants
HATK_WORKFLOW_STEPS = [
    "1. IMGT2Seq - Database processing",
    "2. HLA2HPED - HLA data conversion", 
    "3. NomenCleaner - Nomenclature cleaning",
    "4. BmarkerGenerator - Binary marker generation",
    "5. Analyzer - Association testing",
    "6a. StepwiseRegression - Conditional analysis",
    "6b. OmnibusTest - Omnibus testing", 
    "6c. MetaAnalysis - Meta-analysis"
]

SUPPORTED_ANALYSES = [
    "Single-trait association testing",
    "Multi-trait association testing",
    "Stepwise conditional regression",
    "Omnibus testing with imputation data",
    "Meta-analysis across studies"
]


def get_hatk_info() -> dict:
    """
    Get comprehensive information about HATK toolkit
    
    Returns:
        Dictionary with toolkit information
    """
    return {
        "name": "HLAgent HATK (HLA Analysis Toolkit)",
        "version": __version__,
        "author": __author__,
        "license": __license__,
        "workflow_steps": HATK_WORKFLOW_STEPS,
        "supported_analyses": SUPPORTED_ANALYSES,
        "modules": {
            "Imgt2Seq": {
                "status": "Implemented",
                "description": "IMGT database processing",
                "inputs": ["IMGT database files"],
                "outputs": ["HAT file", "HLA dictionaries", "Map tables"]
            },
            "Hla2Hped": {
                "status": "Implemented",
                "description": "HLA typing data conversion",
                "inputs": ["HLA typing results"],
                "outputs": ["HPED files"]
            },
            "NomenCleaner": {
                "status": "Implemented", 
                "description": "HLA nomenclature standardization",
                "inputs": ["HPED files"],
                "outputs": ["CHPED files"]
            },
            "BmarkerGenerator": {
                "status": "Implemented",
                "description": "Binary marker generation",
                "inputs": ["CHPED files", "HLA dictionaries"],
                "outputs": ["PLINK files", "Beagle files"]
            },
            "BmarkerRegression": {
                "status": "Implemented",
                "description": "Regression analysis",
                "inputs": ["Binary markers", "Phenotype data"],
                "outputs": ["Regression results"]
            },
            "BMarkerStepwiseRegression": {
                "status": "Implemented",
                "description": "Step wise conditional regression analysis",
                "inputs": ["Binary markers", "Phenotype data"],
                "outputs": ["Step wise conditional regression analysis results"]
            },
            "OmnibusTest": {
                "status": "Implemented",
                "description": "Omnibus testing",
                "inputs": ["Association results", "CookHLA data"],
                "outputs": ["Omnibus test results"]
            },
            "MetaAnalysis": {
                "status": "Implemented",
                "description": "Cross-study meta-analysis",
                "inputs": ["Multiple association results"],
                "outputs": ["Meta-analysis results"]
            }
        },
        "capabilities": [
            "Conversational interface",
            "A2A protocol support",
            "MCP server integration", 
            "Multiprocessing support",
            "Interactive parameter setup",
            "Comprehensive validation",
            "Error handling and recovery"
        ]
    }


def list_available_modules() -> list:
    """
    List all available HATK modules
    
    Returns:
        List of module names with their implementation status
    """
    info = get_hatk_info()
    modules = []
    
    for module_name, module_info in info["modules"].items():
        modules.append({
            "name": module_name,
            "status": module_info["status"],
            "description": module_info["description"]
        })
    
    return modules


class HATKPipeline:
    """
    Complete HATK pipeline manager
    
    This class provides a high-level interface to run the complete
    HATK workflow or individual steps.
    
    TODO: Implement complete pipeline functionality
    """
    
    def __init__(self):
        """Initialize HATK pipeline"""
        self.pipeline_steps = HATK_WORKFLOW_STEPS
        self.current_step = 0
        self.results = {}
    
    def run_step_1_imgt2seq(self, config: dict):
        """
        Run Step 1: IMGT2Seq processing
        
        Args:
            config: IMGT2Seq configuration
            
        Returns:
            IMGT2Seq output

        TODO: Implement complete pipeline
        """
        raise NotImplementedError("Pipeline integration pending")
    
    def run_complete_pipeline(self, initial_config: dict):
        """
        Run the complete HATK pipeline
        
        Args:
            initial_config: Initial configuration dictionary
            
        TODO: Implement complete pipeline
        """
        raise NotImplementedError("Complete pipeline not yet implemented")
    
    def get_step_info(self, step_number: int) -> dict:
        """Get information about a specific pipeline step"""
        if 1 <= step_number <= len(self.pipeline_steps):
            return {
                "step_number": step_number,
                "description": self.pipeline_steps[step_number - 1],
                "status": "implemented" if step_number == 1 else "todo"
            }
        else:
            raise ValueError(f"Invalid step number: {step_number}")


# Module initialization message
def _show_welcome_message():
    """Show welcome message when module is imported"""
    print("=" * 60)
    print("HLAgent HATK (HLA Analysis Toolkit) v1.0.0")
    print("=" * 60)  
    print(f"\nFor more information: hatk.get_hatk_info()")
    print("=" * 60)


# Show welcome message on import (can be disabled by setting environment variable)
import os
if not os.environ.get('HATK_SILENT_IMPORT', False):
    _show_welcome_message()
