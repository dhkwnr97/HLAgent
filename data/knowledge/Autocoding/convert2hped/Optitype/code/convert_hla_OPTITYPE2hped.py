# -*- coding: utf-8 -*-

import os, sys, re
import argparse, textwrap
import pandas as pd
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
    if allele == "0" or pd.isna(allele):
        return "0"
    
    # Extract the allele part after the gene name and asterisk
    # Pattern: GENE*XX:YY -> XXYY
    match = re.match(r'^[A-Z0-9]+\*(\d{2}):(\d{2})', str(allele))
    if match:
        return match.group(1) + match.group(2)
    else:
        # If pattern doesn't match, return the original allele
        return str(allele)


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
    
    return common_prefix if common_prefix else "optitype"


class HATK_OPTITYPE2HPED(object):

    def __init__(self, _rhped, _out):

        if not _rhped:
            print(std_ERROR_MAIN_PROCESS_NAME + "Raw hped file(s) wasn't(weren't) given.")
            sys.exit()

        self.result = convert_optitype_to_hped(_rhped, _out)

    def getResult(self):
        return self.result


def convert_optitype_to_hped(_i_HLA, _out):
    """
    Convert OptiType HLA imputation output files to .hped format.
    
    Args:
        _i_HLA: List of TSV input files from OptiType or list of directories containing TSV files
        _out: Output file prefix
    
    Returns:
        str: Path to the generated .hped file
    """
    
    ########## < Argument Checking. > ##########
    
    # Preparing intermediate paths.
    _out = _out if not _out.endswith('/') else _out.rstrip('/')
    if bool(os.path.dirname(_out)): 
        os.makedirs(os.path.dirname(_out), exist_ok=True)

    # Process input files or directories
    l_SampleID = []
    l_HLA = []

    for input_item in _i_HLA:
        if os.path.isfile(input_item):
            # If it's a file, process it directly
            sample_id = os.path.splitext(os.path.basename(input_item))[0]
            # Remove common suffixes like "_result"
            sample_id = re.sub(r'_result$', '', sample_id)
            tsv_file = input_item
        elif os.path.isdir(input_item):
            # If it's a directory, find the TSV file inside and use directory name as sample ID
            sample_id = os.path.basename(input_item)
            tsv_files = glob.glob(os.path.join(input_item, "*.tsv"))
            if not tsv_files:
                print(std_WARNING_MAIN_PROCESS_NAME + f"No TSV files found in directory: {input_item}")
                continue
            tsv_file = tsv_files[0]  # Use the first TSV file found
        else:
            print(std_WARNING_MAIN_PROCESS_NAME + f"Input item not found: {input_item}")
            continue

        # Read the TSV file
        try:
            df = pd.read_csv(tsv_file, sep='\t', index_col=0)
            
            # Extract HLA alleles from the first row (index 0)
            if len(df) == 0:
                print(std_WARNING_MAIN_PROCESS_NAME + f"Empty TSV file: {tsv_file}")
                continue
            row = df.iloc[0]
            
            # OptiType outputs A1, A2, B1, B2, C1, C2
            # We need to map these to our HLA_names order: ["A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1"]
            l_eachRows = []
            
            # A alleles
            a1 = convert_hla_allele_format(row.get('A1', '0'))
            a2 = convert_hla_allele_format(row.get('A2', '0'))
            l_eachRows.extend([a1, a2])
            
            # B alleles
            b1 = convert_hla_allele_format(row.get('B1', '0'))
            b2 = convert_hla_allele_format(row.get('B2', '0'))
            l_eachRows.extend([b1, b2])
            
            # C alleles
            c1 = convert_hla_allele_format(row.get('C1', '0'))
            c2 = convert_hla_allele_format(row.get('C2', '0'))
            l_eachRows.extend([c1, c2])
            
            # DPA1, DPB1, DQA1, DQB1, DRB1 - OptiType doesn't provide these, so set to 0
            for _ in range(5):  # 5 missing HLA genes * 2 alleles each = 10 zeros
                l_eachRows.extend(["0", "0"])
            
            l_SampleID.append(sample_id)
            l_HLA.append(l_eachRows)
            
        except Exception as e:
            print(std_ERROR_MAIN_PROCESS_NAME + f"Error processing file {tsv_file}: {e}")
            continue

    if not l_SampleID:
        print(std_ERROR_MAIN_PROCESS_NAME + "No valid samples were processed.")
        sys.exit(1)

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
    config_file_path = "src/tools/file_handlers/convert_hla_OPTITYPE2hped_run_config.yaml"

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
            # Find all directories in the input directory path
            # Each directory represents a sample and should contain TSV files
            if os.path.isdir(input_dir_path):
                input_files = []
                for item in os.listdir(input_dir_path):
                    item_path = os.path.join(input_dir_path, item)
                    if os.path.isdir(item_path):
                        input_files.append(item_path)
                
                if not input_files:
                    raise ValueError(f"No directories found in: {input_dir_path}")
            else:
                raise ValueError(f"Input directory path does not exist: {input_dir_path}")
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
        convert_optitype_to_hped(input_files, output_prefix)
    else:
        # This else block should theoretically not be reached due to the ValueError checks above
        print(std_ERROR_MAIN_PROCESS_NAME + "An unknown error occurred with configuration parameters.")
        sys.exit(1)


    # Original argparse code (commented out as it's no longer needed for primary execution)
    # parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
    #                                  description=textwrap.dedent('''\
    # #################################################################################################

    #     < OPTITYPE2hped.py >

    #      This Converts the output results from OptiType HLA imputation software to *.hped format.
    #     
    #      The number of raw input files to make a hped file can be 1 or more.
    #     
    #      Input files should be TSV format output files from OptiType software.
    #     
    #      The TSV files should contain HLA allele information with columns A1, A2, B1, B2, C1, C2.
    #     
    #      HLA alleles are converted from full format (e.g., "A*01:01") to shortened format (e.g., "0101").
    #     
    # #################################################################################################
    #                                      '''),
    #                                      add_help=False)

    # parser._optionals.title = "OPTIONS"

    # parser.add_argument("-h", "--help", help="\nShow this help message and exit\n\n", action='help')
    # parser.add_argument("-rhped", help="\nInput Data files (OptiType TSV output files)\n\n", nargs='+', required=True)
    # parser.add_argument("--out", "-o", help="\nOutput file prefix\n\n", required=True)

    # args = parser.parse_args()
    # print(args)

    # Main function execution
    # convert_optitype_to_hped(args.rhped, args.out) 

