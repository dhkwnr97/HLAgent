# -*- coding: utf-8 -*-

import os, sys, re
import argparse, textwrap
import pandas as pd
import yaml
import glob

########## < Core Global Variables > ##########

std_MAIN_PROCESS_NAME = "\n[%s]: " % (os.path.basename(__file__))
std_ERROR_MAIN_PROCESS_NAME = "\n[%s::ERROR]: " % (os.path.basename(__file__))
std_WARNING_MAIN_PROCESS_NAME = "\n[%s::WARNING]: " % (os.path.basename(__file__))

### General
HLA_names = ["A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1"]
isREVERSE = {'A': False, 'C': True, 'B': True, 'DRB1': True, 'DQA1': False, 'DQB1': True, 'DPA1': True, 'DPB1': False}


def convert_hla_allele_format(allele):
    """
    Convert HLA allele from full format (e.g., "HLA-A*01:01:01") to shortened format (e.g., "0101").
    
    Args:
        allele: HLA allele string in full format or "-" or "Not typed"
    
    Returns:
        str: HLA allele in shortened format, or "0" if input is "-", "Not typed", or empty
    """
    if allele in ["-", "Not typed", "", "0"]:
        return "0"
    
    # Extract the allele part after the gene name and asterisk
    # Pattern: HLA-GENE*XX:YY:ZZ -> XXYY (only first two fields)
    match = re.match(r'^HLA-[A-Z0-9]+\*(\d{2}):(\d{2})', allele)
    if match:
        return match.group(1) + match.group(2)
    else:
        # If pattern doesn't match, return "0"
        return "0"


def find_common_prefix(file_paths):
    """
    Find the common prefix from a list of file paths.
    
    Args:
        file_paths: List of file paths
    
    Returns:
        str: Common prefix of the file basenames
    """
    if not file_paths:
        return "hlahd"
    
    # Get basenames without extensions
    basenames = [os.path.splitext(os.path.basename(path))[0] for path in file_paths]
    
    if len(basenames) == 1:
        return basenames[0]
    
    # Find common prefix
    common_prefix = ""
    min_length = min(len(name) for name in basenames)
    
    for i in range(min_length):
        char = basenames[0][i]
        if all(name[i] == char for name in basenames):
            common_prefix += char
        else:
            break
    
    # Remove trailing non-alphanumeric characters
    common_prefix = re.sub(r'[^a-zA-Z0-9]+$', '', common_prefix)
    
    return common_prefix if common_prefix else "hlahd"


class HATK_HLAHD2HPED(object):

    def __init__(self, _rhped, _out):

        if not _rhped:
            print(std_ERROR_MAIN_PROCESS_NAME + "Raw hped file(s) wasn't(weren't) given.")
            sys.exit()

        self.result = convert_HLAHD_to_hped(_rhped, _out)

    def getResult(self):
        return self.result


def convert_HLAHD_to_hped(_i_HLA, _out):
    """
    Convert HLAHD HLA imputation output files to .hped format.
    
    Args:
        _i_HLA: List of TXT input files from HLAHD
        _out: Output file prefix
    
    Returns:
        str: Path to the generated .hped file
    """
    
    ########## < Argument Checking. > ##########
    
    # Preparing intermediate paths.
    _out = _out if not _out.endswith('/') else _out.rstrip('/')
    if bool(os.path.dirname(_out)): 
        os.makedirs(os.path.dirname(_out), exist_ok=True)

    l_SampleID = []
    l_HLA = []

    for i in range(0, len(_i_HLA)):
        # Extract sample ID from file path
        # Expected path: .../sampleID/result/sampleID_final.result.txt
        file_path = _i_HLA[i]
        sample_id = os.path.basename(os.path.dirname(os.path.dirname(file_path)))
        l_SampleID.append(sample_id)

        # Read the HLAHD result file
        try:
            with open(file_path, 'r') as f:
                lines = f.readlines()
        except FileNotFoundError:
            print(std_WARNING_MAIN_PROCESS_NAME + f"File not found: {file_path}")
            continue

        # Parse HLAHD results
        hla_results = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            parts = line.split('\t')
            if len(parts) >= 3:
                gene = parts[0]
                allele1 = parts[1]
                allele2 = parts[2]
                
                # Handle "-" in allele2 (means same as allele1)
                if allele2 == "-":
                    allele2 = allele1
                
                hla_results[gene] = [allele1, allele2]

        # Extract HLA alleles for the specified HLA_names
        l_eachRows = []
        for gene in HLA_names:
            if gene in hla_results:
                alleles = hla_results[gene]
                # Convert to shortened format
                alleles_converted = [convert_hla_allele_format(allele) for allele in alleles]
                l_eachRows.extend(alleles_converted)
            else:
                # If gene not found, add "0", "0"
                l_eachRows.extend(["0", "0"])

        l_HLA.append(l_eachRows)

    ### DataFrame
    df_RETURN = pd.DataFrame(l_HLA)

    ### Index
    l_idx_RETURN = []

    # (1) FamID
    l_idx_RETURN.append(["FamID_"+str(i) for i in range(0, len(l_SampleID))])

    # (2) SampleID
    l_idx_RETURN.append(l_SampleID)

    # (3), (4), (5) : P_ID, M_ID, Sex(Unknown default)
    idx_temp = ["0" for i in range(0, len(l_SampleID))]
    l_idx_RETURN.append(idx_temp)
    l_idx_RETURN.append(idx_temp)
    l_idx_RETURN.append(idx_temp)

    # (6) Phe (Unknown default.)
    idx_temp = ["-9" for i in range(0, len(l_SampleID))]
    l_idx_RETURN.append(idx_temp)

    idx_REUTURN = pd.MultiIndex.from_arrays(l_idx_RETURN)
    df_RETURN.index = idx_REUTURN

    ### Exporting(File Writing)
    df_RETURN.to_csv(_out+".hped", sep='\t', header=False, index=True)

    return _out+".hped"


if __name__ == "__main__":
    # Path to the run configuration file
    config_file_path = "src/tools/file_handlers/convert_hla_HLAHD2hped_run_config.yaml"

    # Load parameters from the YAML file
    try:
        with open(config_file_path, 'r') as config_file:
            config = yaml.safe_load(config_file)

        # Get input and output paths from the config file
        input_files = config.get('_input_files')
        if input_files is None:
            input_files = []
        input_dir_path = config.get('_input_dir_path')
        output_base_path = config.get('_output_path')

        # Determine input files
        if input_files is not None and input_files:
            pass  # Use as is
        elif input_dir_path is not None:
            # Find all directories in the input path, then look for final.result.txt files
            input_files = []
            if os.path.exists(input_dir_path):
                for item in os.listdir(input_dir_path):
                    sample_dir = os.path.join(input_dir_path, item)
                    if os.path.isdir(sample_dir):
                        # Look for result directory
                        result_dir = os.path.join(sample_dir, 'result')
                        if os.path.exists(result_dir):
                            # Look for final.result.txt files
                            result_files = glob.glob(os.path.join(result_dir, '*final.result.txt'))
                            input_files.extend(result_files)
            
            if not input_files:
                raise ValueError(f"No *final.result.txt files found in directories under: {input_dir_path}")
        else:
            raise ValueError("Either '_input_files' or '_input_dir_path' must be specified in the configuration file.")

        if not output_base_path:
            raise ValueError("'_output_path' is missing in the configuration file.")

        # Generate output file name using common prefix from input files
        common_prefix = find_common_prefix(input_files)
        output_prefix = os.path.join(output_base_path, common_prefix)

    except FileNotFoundError:
        print(std_ERROR_MAIN_PROCESS_NAME + f"Configuration file not found at {config_file_path}")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(std_ERROR_MAIN_PROCESS_NAME + f"Error parsing YAML file: {e}")
        sys.exit(1)
    except ValueError as e:
        print(std_ERROR_MAIN_PROCESS_NAME + f"Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        print(std_ERROR_MAIN_PROCESS_NAME + f"An unexpected error occurred: {e}")
        sys.exit(1)

    # Main function execution with parameters from the config file
    if input_files and output_prefix:
        convert_HLAHD_to_hped(input_files, output_prefix)
    else:
        # This else block should theoretically not be reached due to the ValueError checks above
        print(std_ERROR_MAIN_PROCESS_NAME + "An unknown error occurred with configuration parameters.")
        sys.exit(1)
