"""
Agent types for File Converter Agent.

Defines data structures and enums used by the file converter agent.
"""
import os
from dotenv import load_dotenv
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


load_dotenv()


class ConverterState(Enum):
    """State enumeration for file converter agent."""
    IDLE = "idle"
    CHOOSING_MODE = "choosing_mode"
    GENOTYPE_CONVERSION = "genotype_conversion"
    IMPUTATION_CONVERSION = "imputation_conversion"
    PROCESSING = "processing"
    COMPLETED = "completed"
    ERROR = "error"


class ResponseType(Enum):
    """Response type enumeration."""
    INFO = "info"
    REQUEST_INPUT = "request_input"
    SUCCESS = "success"
    ERROR = "error"
    COMPLETION = "completion"


class ConversionMode(Enum):
    """Conversion mode enumeration."""
    GENOTYPE = "genotype"
    IMPUTATION = "imputation"


class GenotypeFunction(Enum):
    """Genotype conversion function enumeration."""
    VARIOUS_TO_PLINK = "function1"  # Various formats to .bed/.bim/.fam
    BEAGLE_TO_VCF = "function2"     # Beagle v3 to VCF v4.1
    VCF_TO_BEAGLE = "function3"     # VCF v4.1 to Beagle v3


@dataclass
class ConverterResponse:
    """Response structure for converter agent."""
    response_type: ResponseType
    message: str
    requires_input: bool = False
    session_complete: bool = False
    data: Optional[Dict[str, Any]] = None


@dataclass
class ConversionRequest:
    """Request structure for file conversion."""
    conversion_mode: ConversionMode
    function_type: Optional[str] = None
    input_files: List[str] = None
    output_directory: str = os.path.join(os.getenv("HLAGENT_MAIN_DIRECTORY"), "data/output/ConvertGT")
    parameters: Dict[str, Any] = None


@dataclass
class GenotypeConversionRequest:
    """Request structure for genotype conversion."""
    function: GenotypeFunction
    input_extensions: List[str]
    output_extensions: List[str]
    input_files: List[str] = None
    parameters: Dict[str, Any] = None


@dataclass
class ImputationTool:
    """Information about available HLA imputation conversion tools."""
    name: str
    display_name: str
    script_path: str
    config_path: str
    description: str