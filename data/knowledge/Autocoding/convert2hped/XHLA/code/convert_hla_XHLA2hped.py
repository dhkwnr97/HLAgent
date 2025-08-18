# -*- coding: utf-8 -*-

import os, sys, re
import argparse, textwrap
import pandas as pd
import json
import yaml # Import the yaml library
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
    Convert HLA allele from full format (e.g., "A*01:01") to shortened format (e.g., "0101").
    
    Args:
        allele: HLA allele string in full format
    
    Returns:
        str: HLA allele in shortened format, or "0" if input is "0"
    """
    if allele == "0":
        return "0"
    
    # Extract the allele part after the gene name and asterisk
    # Pattern: GENE*XX:YY -> XXYY
    match = re.match(r'^[A-Z0-9]+\*(\d{2}):(\d{2})', allele)
    if match:
        return match.group(1) + match.group(2)
    else:
        # If pattern doesn't match, return the original allele
        return allele


def find_common_prefix(file_paths):
    """
    Find the common prefix from a list of file paths.
    
    Args:
        file_paths: List of file paths
    
    Returns:
        str: Common prefix of the file basenames
    """
    if not file_paths:
        return "output"
    
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
    
    return common_prefix if common_prefix else "xhla"


class HATK_XHLA2HPED(object):

    def __init__(self, _rhped, _out):

        if not _rhped:
            print(std_ERROR_MAIN_PROCESS_NAME + "Raw hped file(s) wasn't(weren't) given.")
            sys.exit()

        self.result = convert_xHLA_to_hped(_rhped, _out)

    def getResult(self):
        return self.result


def convert_xHLA_to_hped(_i_HLA, _out):
    """
    Convert xHLA HLA imputation output files to .hped format.
    
    Args:
        _i_HLA: List of JSON input files from xHLA
        _out: Output file prefix
    
    Returns:
        str: Path to the generated .hped file
    """
    
    ########## < Argument Checking. > ##########
    
    # Preparing intermediate paths.
    _out = _out if not _out.endswith('/') else _out.rstrip('/')
    if bool(os.path.dirname(_out)): 
        os.makedirs(os.path.dirname(_out), exist_ok=True)

    # It Assumes that json files are more than 1.
    DICT_json = []

    for i in range(0, len(_i_HLA)):
        with open(_i_HLA[i]) as f:
            DICT_json.append(json.load(f))

    """
    The output file from xHLA has 6 keys.
    
    (1) "subject_id"
    (2) "creation_time"
    (3) "report_version"
    (4) "report_type"
    (5) "sample_id"
    (6) "hla"
    
    Here, It will be assumed that "subject_id" is same to "sample_id". 
    """

    l_SampleID = []
    l_HLA = []

    for i in range(0, len(_i_HLA)):
        l_SampleID.append(DICT_json[i]["subject_id"])

        l_temp = DICT_json[i]["hla"]["alleles"]
        l_eachRows = []

        for j in range(0, len(HLA_names)):
            l_temp2 = list(filter(lambda x : re.match(''.join(["^", HLA_names[j], r"\*"]), x), l_temp))
            l_temp2 = ["0", "0"] if not bool(l_temp2) else l_temp2
            
            # Convert HLA alleles to shortened format
            l_temp2_converted = [convert_hla_allele_format(allele) for allele in l_temp2]
            l_eachRows.extend(l_temp2_converted)

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
    config_file_path = "src/tools/file_handlers/convert_hla_XHLA2hped_run_config.yaml"

    # Load parameters from the YAML file
    try:
        with open(config_file_path, 'r') as config_file:
            config = yaml.safe_load(config_file)

        # Get input and output paths from the config file
        input_files = config.get('_input_files')
        input_dir_path = config.get('_input_dir_path')
        output_base_path = config.get('_output_path')

        # Determine input files
        if input_files:
            pass  # Use as is
        elif input_dir_path:
            # Find all .json files in the directory
            input_files = sorted(glob.glob(os.path.join(input_dir_path, '*.json')))
            if not input_files:
                raise ValueError(f"No .json files found in directory: {input_dir_path}")
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
        convert_xHLA_to_hped(input_files, output_prefix)
    else:
        # This else block should theoretically not be reached due to the ValueError checks above
        print(std_ERROR_MAIN_PROCESS_NAME + "An unknown error occurred with configuration parameters.")
        sys.exit(1)


    # Original argparse code (commented out as it's no longer needed for primary execution)
    # parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
    #                                  description=textwrap.dedent('''\
    # #################################################################################################

    #     < XHLA2hped.py >

    #      This Converts the output results from xHLA HLA imputation software to *.hped format.
    #     
    #      The number of raw input files to make a hped file can be 1 or more.
    #     
    #      Input files should be JSON format output files from xHLA software.
    #     
    #      The JSON files should contain HLA allele information in the "hla" key.
    #     
    #      HLA alleles are converted from full format (e.g., "A*01:01") to shortened format (e.g., "0101").
    #     
    # #################################################################################################
    #                                      '''),
    #                                      add_help=False)

    # parser._optionals.title = "OPTIONS"

    # parser.add_argument("-h", "--help", help="\nShow this help message and exit\n\n", action='help')
    # parser.add_argument("-rhped", help="\nInput Data files (xHLA JSON output files)\n\n", nargs='+', required=True)
    # parser.add_argument("--out", "-o", help="\nOutput file prefix\n\n", required=True)

    # args = parser.parse_args()
    # print(args)

    # Main function execution
    # convert_xHLA_to_hped(args.rhped, args.out) 