# -*- coding: utf-8 -*-

import os, sys, re
import argparse, textwrap
import pandas as pd
import yaml

########## < Core Global Variables > ##########

std_MAIN_PROCESS_NAME = "\n[%s]: " % (os.path.basename(__file__))
std_ERROR_MAIN_PROCESS_NAME = "\n[%s::ERROR]: " % (os.path.basename(__file__))
std_WARNING_MAIN_PROCESS_NAME = "\n[%s::WARNING]: " % (os.path.basename(__file__))

### General
HLA_names = ["A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1"]
isREVERSE = {'A': False, 'C': True, 'B': True, 'DRB1': True, 'DQA1': False, 'DQB1': True, 'DPA1': True, 'DPB1': False}


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
    
    return common_prefix if common_prefix else "axiom"


class HATK_AXIOM2HPED(object):

    def __init__(self, _rhped, _out):

        if not _rhped:
            print(std_ERROR_MAIN_PROCESS_NAME + "Raw hped file(s) wasn't(weren't) given. Please check '--rhped' argument again.")
            sys.exit()

        self.result = convert_AXIOM_to_hped(_rhped, _out)

    def getResult(self):
        return self.result


def convert_AXIOM_to_hped(_rhped, _out):
    """
    Convert AXIOM HLA imputation output files to .hped format.
    
    Args:
        _rhped: List of 8 input files (one for each HLA gene)
        _out: Output file prefix
    
    Returns:
        str: Path to the generated .hped file
    """
    
    ########## < Argument Checking. > ##########
    
    # Preparing intermediate paths.
    _out = _out if not _out.endswith('/') else _out.rstrip('/')
    if bool(os.path.dirname(_out)): 
        os.makedirs(os.path.dirname(_out), exist_ok=True)

    if len(_rhped) != 8:
        print(std_ERROR_MAIN_PROCESS_NAME + "Platform \"{0}\" needs 8 input files. Please check it again.\n".format("AXIOM"))
        sys.exit()

    ### Exception handling 1 - When every rhped is 'NA'.
    f_isNA = list(map(lambda x : x == 'NA', _rhped))

    if all(f_isNA):
        print(std_ERROR_MAIN_PROCESS_NAME + "No any AXIOM output file has been given. Please check the '--rhped' argument again.")
        sys.exit()

    first_appear = -1
    for i in range(len(HLA_names)):
        if not f_isNA[i]:
            first_appear = i
            break

    DICT_rhped = {HLA_names[i]: pd.read_csv(_rhped[i], header=None, sep=r'\s+', dtype=str, 
                                           names=["IID", "idx", "4digit", "p1", "p2"], 
                                           usecols=['IID', 'idx', '4digit']) if not f_isNA[i] 
                  else pd.DataFrame([]) for i in range(0, len(HLA_names))}

    ### Restructuring rhped
    for i in range(len(HLA_names)):
        if not f_isNA[i]:
            DICT_rhped[HLA_names[i]] = DICT_rhped[HLA_names[i]].set_index(['IID', 'idx']).unstack(['idx'])

    ### Exception handling 2 - When there is any rhped which has different number of rows.
    L = [DICT_rhped[HLA_names[i]].shape[0] for i in range(len(HLA_names)) if not f_isNA[i]]
    if len(set(L)) > 1:
        print(std_ERROR_MAIN_PROCESS_NAME + "There is an AXIOM output file which has different number of rows."
                                            "Please check the AXIOM output files given to the '--rhped' argument.")
        sys.exit()
    else:
        L = L.pop()

    ### The Main step to generate hped file.
    l_HLA = []

    for i in range(len(HLA_names)):
        if not f_isNA[i]:
            df_temp = DICT_rhped[HLA_names[i]].reset_index(drop=True)
        else:
            df_temp = pd.DataFrame([['0', '0'] for z in range(L)])

        df_temp.columns = [HLA_names[i]+'_1', HLA_names[i]+'_2']
        l_HLA.append(df_temp)

    df_Right = pd.concat(l_HLA, axis=1)

    ### Meta information(Left 6 columns)
    sr_PID = pd.Series(['0' for z in range(L)])
    sr_MID = pd.Series(['0' for z in range(L)])
    sr_Sex = pd.Series(['0' for z in range(L)])
    sr_Phe = pd.Series(['-9' for z in range(L)])

    df_Left = pd.concat([DICT_rhped[HLA_names[first_appear]].index.to_frame(index=False),
                         DICT_rhped[HLA_names[first_appear]].index.to_frame(index=False),
                         sr_PID, sr_MID, sr_Sex, sr_Phe], axis=1)

    df_HPED_axiom = pd.concat([df_Left, df_Right], axis=1)
    df_HPED_axiom.to_csv(_out+'.hped', sep='\t', header=False, index=False)

    return _out+'.hped'


if __name__ == "__main__":
    # Path to the run configuration file
    config_file_path = "src/tools/file_handlers/convert_hla_AXIOM2hped_run_config.yaml"

    # Load parameters from the YAML file
    try:
        with open(config_file_path, 'r') as config_file:
            config = yaml.safe_load(config_file)
        
        # Get input and output paths from the config file
        input_files = config.get('_input_files')
        output_base_path = config.get('_output_path')

        if not input_files:
            raise ValueError("'_input_files' is missing or empty in the configuration file.")
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
        convert_AXIOM_to_hped(input_files, output_prefix)
    else:
        print(std_ERROR_MAIN_PROCESS_NAME + "An unknown error occurred with configuration parameters.")
        sys.exit(1)


    # Original argparse code (commented out as it's no longer needed for primary execution)
    # parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter,
    #                                  description=textwrap.dedent('''\
    # #################################################################################################

    #     < AXIOM2hped.py >

    #      This Converts the output results from AXIOM HLA imputation software to *.hped format.
    #     
    #      The number of raw input files to make a hped file must be 8.
    #     
    #      The 8 AXIOM output files must be given with the below order:
    #      (8 HLA genes - "A", "B", "C", "DPA1", "DPB1", "DQA1", "DQB1", "DRB1").
    #     
    #      Usage: Use "NA" for missing HLA gene files.
    #     
    # #################################################################################################
    #                                      '''),
    #                                      add_help=False)

    # parser._optionals.title = "OPTIONS"

    # parser.add_argument("-h", "--help", help="\nShow this help message and exit\n\n", action='help')
    # parser.add_argument("-rhped", help="\nInput Data files (8 AXIOM output files)\n\n", nargs=8, required=True)
    # parser.add_argument("--out", "-o", help="\nOutput file prefix\n\n", required=True)

    # args = parser.parse_args()
    # print(args)

    # # Main function execution
    # convert_AXIOM_to_hped(args.rhped, args.out) 