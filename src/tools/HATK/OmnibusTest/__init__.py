#!/usr/bin/env python3
#-*- coding: utf-8 -*-

"""
Omnibus Test module.

"""

import os
import subprocess as sbp
from os.path import dirname

from src.tools.HATK.src.HATK_Error import HATK_R_Execution_Error
from src.tools.HATK.src.util import Exists, findExec

std_ERROR = "\n[OmnibusTest::ERROR]: "

def generate_aa_from_phased(fam_file: str, bgl_phased_file: str, output_prefix: str, save_intermediates: bool = False):
    """
    Generates an amino acid (.aa) file from a phased BEAGLE file.

    This function calls an R script to perform the conversion, which is a required
    preprocessing step for the Omnibus Test when conditioning on variants.

    Args:
        fam_file (str): Path to the PLINK .fam file.
        bgl_phased_file (str): Path to the phased BEAGLE file (*.bgl.phased).
        output_prefix (str): The prefix for output files. The .aa file will be
                             named based on this prefix.
        save_intermediates (bool): If True, intermediate log files are kept.

    Returns:
        str: The path to the generated .aa file.
    """
    Rscript = findExec("Rscript", std_ERROR + "'Rscript' command can't be found. Please install R.")
    
    # The R script path is relative to the HATK tools directory
    r_script_path = os.path.join(dirname(__file__), "src", "AllCC_Get_Phased_AA_Calls.R")

    if not os.path.exists(r_script_path):
         # Look for it relative to the OmnibusTest directory if the above fails
         r_script_path_alt = os.path.join(os.path.dirname(__file__), "OmnibusTest", "src", "AllCC_Get_Phased_AA_Calls.R")
         if os.path.exists(r_script_path_alt):
             r_script_path = r_script_path_alt
         else:
            raise FileNotFoundError(f"OmnibusTest R script not found at {r_script_path}")

    command = f"{Rscript} {r_script_path} {bgl_phased_file} {fam_file} {output_prefix}"
    
    log_file = output_prefix + '.aa.log'
    try:
        with open(log_file, 'w') as f_log:
            sbp.run(command.split(), check=True, stdout=f_log, stderr=f_log)

    except sbp.CalledProcessError:
        raise HATK_R_Execution_Error(
            f"{std_ERROR}Failed to preprocess the phased beagle file ('{bgl_phased_file}').\n"
            f"Please check the log file ('{log_file}')."
        )
    else:
        if Exists(log_file) and not save_intermediates:
            os.remove(log_file)
        
        aa_file = output_prefix + '.aa'
        if not Exists(aa_file):
            raise FileNotFoundError(f"Expected output .aa file not found: {aa_file}")
            
        return aa_file

__all__ = [
    "generate_aa_from_phased"
]