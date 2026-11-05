#-*- coding: utf-8 -*-

import os, sys
import re
from shutil import which

from .PLINK_Bash import Bash_RUN_PLINK
from hatk_port.Phasing.src.BEAGLE_Bash import Bash_BEAGLE

def _convert_memory_format(java_mem, jar_path):
    """
    Convert memory format for Java jar files.
    Jar files typically expect megabytes in decimal (e.g., -Xmx8000m for 8GB)
    
    Args:
        java_mem: Memory string (e.g., '8g', '8000m', '4G')
        jar_path: Path to jar file
        
    Returns:
        str: Memory string in MB format (decimal)
    """
    # Convert GB to MB if needed (decimal: 1000)
    if 'g' in java_mem.lower():
        # Extract number and convert GB to MB
        num = re.search(r'(\d+)', java_mem)
        if num:
            gb_value = int(num.group(1))
            mb_value = gb_value * 1000  # Decimal conversion: 8GB = 8000MB
            return f"{mb_value}m"
    # If already in MB format, return as is
    elif 'm' in java_mem.lower():
        return java_mem
    else:
        # Assume it's a number in GB
        try:
            gb_value = int(java_mem)
            mb_value = gb_value * 1000  # Decimal conversion
            return f"{mb_value}m"
        except ValueError:
            # Default to 1GB = 1000MB (decimal)
            return "1000m"
    
    return java_mem


def PLINK2BEAGLE(_bfile, _out_prefix, _linkage2beagle, plink=which("plink"),
                 _java=which("java"), _java_mem='1G', _f_save_intermediates=False, _f_CookHLA_REF=False):

    ### Main Variables ###
    _bim = _bfile+'.bim'

    _map = None
    _ped = None

    _dat = None
    _ped_nopheno = None

    _markers = _out_prefix+'.markers'
    _bgl = _out_prefix+'.bgl'


    ### Main Actions ###

    # *.markers
    if _f_CookHLA_REF:
        command = ' '.join(["awk", '\'{print $2 " " $4 " " $5 " " $6}\'', _bim, ">", _markers])
    else:
        command = ' '.join(["awk", '\'{print $2 " " $4 " " $6 " " $5}\'', _bim, ">", _markers]) # effect allele(a1-allele / ALT allele) as the 4th column. (2022.03.17.)
    # print(command)
    os.system(command)

    # *.{dat,nopheno.ped}
    command = "{plink} --recode --bfile {bfile} --keep-allele-order --alleleACGT --out {out}" \
                .format(plink=plink, bfile=_bfile, out=_out_prefix)
    # print(command)
    Bash_RUN_PLINK(command, _out_prefix)

    _ped = _out_prefix+'.ped'
    _map = _out_prefix+'.map'

    command = ' '.join(["awk", '\'{print "M " $2}\'', _map, ">", _out_prefix+'.dat'])
    # print(command)
    os.system(command)

    _dat = _out_prefix+'.dat'

    command = ' '.join(["cut -d ' ' -f1-5,7-", _ped, ">", _out_prefix+'.nopheno.ped'])
    # print(command)
    os.system(command)

    _ped_nopheno = _out_prefix+'.nopheno.ped'

    # Convert memory format for Java jar files (always use MB)
    java_mem_formatted = _convert_memory_format(_java_mem, _linkage2beagle)

    # Main Conversion (linkage2beagle.jar)
    command = "{java} -Xmx{java_mem} -jar {l2b} {data} {ped_nopheno}" \
                .format(java=_java, java_mem=java_mem_formatted, l2b=_linkage2beagle, data=_dat, ped_nopheno=_ped_nopheno)
    # print(command)
    Bash_BEAGLE(command, _bgl)



    if not _f_save_intermediates:
        os.remove(_ped)
        os.remove(_map)

        os.remove(_ped_nopheno)
        os.remove(_dat)


    return _bgl, _markers



if __name__ == '__main__':

    """
    PLINK2BEAGLE.py
    : Conversion from PLINK genotype to BEAGLE(v3.x) file format.
    
    """

    # bfile = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset"
    # out_prefix = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt"

    bfile = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.chr6.hg18.29-34mb"
    out_prefix = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.chr6.hg18.29-34mb"
    l2b = "/home/wansonchoi/sf_VirtualBox_Share/HATK/dependency/linkage2beagle.jar"

    PLINK2BEAGLE(bfile, out_prefix, l2b)