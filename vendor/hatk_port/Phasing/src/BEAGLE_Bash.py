#-*- coding: utf-8 -*-

import os, sys, re
from os.path import exists, join
import subprocess as sbp

from hatk_port.src.HATK_Error import HATK_BEAGLE_Execution_Error
from hatk_port.src.util import Exists

def Bash_BEAGLE(_command, _out, _f_save_log=False):
    try:
        with open(_out, 'w') as f_out, open(_out + '.log', 'w') as f_out_log:
            sbp.run(_command.split(), check=True, stdout=f_out, stderr=f_out_log)

    except sbp.CalledProcessError:
        raise HATK_BEAGLE_Execution_Error(
            "\nNext BEAGLE execution failed. ('{}')".format(_command) + \
            ("\nPlease refer to its log file. ('{}')".format(_out + '.log') if Exists(_out + '.log') else "")
        )
    else:
        if Exists(_out + '.log') and not _f_save_log: os.remove(_out + '.log')
        return _out



def Bash_BEAGLE_Phase(_command, _out, _f_save_log=True):
    try:
        with open(_out + '.log', 'w') as f_log, open(_out + '.err', 'w') as f_err:
            result = sbp.run(_command.split(), check=True, stdout=f_log, stderr=f_err, text=True)
        print(f"BEAGLE execution completed successfully")

    except sbp.CalledProcessError as e:
        print(f"BEAGLE execution failed with return code: {e.returncode}")
        
        # Print error details for debugging
        if Exists(_out + '.err'):
            print(f"Error file content:")
            with open(_out + '.err', 'r') as f:
                error_content = f.read()
                print(error_content)
        
        if Exists(_out + '.log'):
            print(f"Log file content:")
            with open(_out + '.log', 'r') as f:
                log_content = f.read()
                print(log_content)
        
        raise HATK_BEAGLE_Execution_Error(
            "\nNext BEAGLE Phasing failed. ('{}')".format(_command) + \
            ("\nPlease refer to its log('{}') file.".format(_out + '.log') if Exists(_out + '.log') else "")
        )
    else:
        if Exists(_out + '.log') and not _f_save_log: os.remove(_out + '.log')
        if Exists(_out + '.err'): os.remove(_out + '.err')
        return _out