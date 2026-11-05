#-*- coding: utf-8 -*-

import os, sys, re
from os.path import basename, dirname, join
import subprocess as sbp
from shutil import which
import gzip

from hatk_port.src.HATK_Error import HATK_BEAGLE_Execution_Error
from hatk_port.Phasing.src.BEAGLE_Bash import Bash_BEAGLE_Phase, Bash_BEAGLE
from hatk_port.Phasing.src.GCtrick.redefineBPv1BH import redefineBP
from hatk_port.Phasing.src.GCtrick.bgl2GC_trick_bgl import Bgl2GC
from hatk_port.Phasing.src.GCtrick.GC_tricked_bgl2ori_bgl import GCtricedBGL2OriginalBGL_2 # type: ignore
from hatk_port.src.util import Exists

std_MAIN = "\n[%s]: " % basename(__file__)
std_ERROR = "\n[%s::ERROR]: " % basename(__file__)
std_WARNING = "\n[%s::WARNING]: " % basename(__file__)


def _convert_memory_format(java_mem, beagle_path):
    """
    Convert memory format based on BEAGLE version.
    
    BEAGLE 3.3.2 expects megabytes in decimal (e.g., -Xmx8000m for 8GB)
    BEAGLE 5.x expects gigabytes (e.g., -Xmx8g)
    
    Args:
        java_mem: Memory string (e.g., '8g', '8000m', '4G')
        beagle_path: Path to BEAGLE executable or jar file
        
    Returns:
        str: Memory string in correct format for the BEAGLE version
    """
    # Check if this is BEAGLE 3.3.2 (jar file)
    if beagle_path and 'beagle.jar' in beagle_path:
        # BEAGLE 3.3.2 uses megabytes in decimal (1000-based)
        # Convert GB to MB if needed
        if 'g' in java_mem.lower():
            # Extract number and convert GB to MB (decimal: 1000)
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
    else:
        # BEAGLE 5.x uses gigabytes
        # Convert MB to GB if needed
        if 'm' in java_mem.lower():
            # Extract number and convert MB to GB
            num = re.search(r'(\d+)', java_mem)
            if num:
                mb_value = int(num.group(1))
                gb_value = mb_value // 1000  # Decimal conversion
                if gb_value == 0:
                    gb_value = 1  # Minimum 1GB
                return f"{gb_value}g"
        # If already in GB format, return as is
        elif 'g' in java_mem.lower():
            return java_mem
        else:
            # Assume it's a number in MB
            try:
                mb_value = int(java_mem)
                gb_value = mb_value // 1000  # Decimal conversion
                if gb_value == 0:
                    gb_value = 1  # Minimum 1GB
                return f"{gb_value}g"
            except ValueError:
                # Default to 1GB
                return "1g"
    
    return java_mem


def GCtrick(_bgl, _markers, _out_dir, _f_save_intermediates=False):

    ### Main Variables ###
    _bgl_GCtrick = join(_out_dir, basename(_bgl)+'.GCtrick')
    _markers_GCtrick = join(_out_dir, basename(_markers)+'.GCtrick')

    _markers_GCtrick_refined = _markers_GCtrick+'.refined'


    ### Main Actions ###

    # GCtrick
    _bgl_GCtrick, _markers_GCtrick = Bgl2GC(_bgl, _markers, _bgl_GCtrick, _markers_GCtrick)
    # G: REF allele / C: ALT allele(effect allele) (2022.03.17.)
    # Now the markers file is generated as the 4th column is the effect allele. (the 3rd is the REF allele.)
    # Previously the relationship was reversed. (ex. CookHLA)

    # refine BPs
    _markers_GCtrick_refined = redefineBP(_markers_GCtrick, _markers_GCtrick_refined)


    if not _f_save_intermediates:
        os.remove(_markers_GCtrick)


    return _bgl_GCtrick, _markers_GCtrick_refined



def BEAGLE2VCF(_bgl_GCtrick, _markers_GCtrick_refined, _out, _beagle2vcf, _java=which("java"), _java_mem='1G',
               _f_save_intermediates=False, _f_gzip=True):

    # Convert memory format for Java commands (always use MB for jar files)
    java_mem_formatted = _convert_memory_format(_java_mem, _beagle2vcf)
    
    command = "{java} -Xmx{java_mem} -jar {beagle2vcf} {chrom} {markers} {bgl} {missing}" \
        .format(java=_java, java_mem=java_mem_formatted, beagle2vcf=_beagle2vcf, chrom='6',
                markers=_markers_GCtrick_refined, bgl=_bgl_GCtrick, missing='0')
    # print(command)
    _vcf_GCtrick = Bash_BEAGLE(command, _out)

    if _f_gzip:
        os.system("gzip -f {}".format(_vcf_GCtrick))
        _vcf_GCtrick = _vcf_GCtrick+'.gz'


    # if not _f_save_intermediates:
    #     os.remove(_bgl_GCtrick)
    #     os.remove(_markers_GCtrick_refined) # should be optional if needed.
    # (2022.03.16.) desirable to remove only the ones generated in the function.


    return _vcf_GCtrick



def Beagle_Phase(_vcf, _out_prefix, _bgl_GCtrick=None, _markers_GCtrick_refined=None, _beagle=which("beagle"), _java_mem='1G', _nthreads=1, _f_save_intermediates=False, _missing='0'):

    ### Main Variables ###
    _vcf_phased = _out_prefix

    ### Main Actions ###
    # Convert memory format based on BEAGLE version
    java_mem_formatted = _convert_memory_format(_java_mem, _beagle)
    
    # Check if this is BEAGLE 3.3.2 (jar file) - uses different parameter format
    if _beagle and 'beagle.jar' in _beagle:
        # BEAGLE 3.3.2 uses: unphased=, markers=, out=, missing=
        # For BEAGLE 3.3.2, use _bgl_GCtrick as unphased and _markers_GCtrick_refined as markers
        unphased_file = _bgl_GCtrick if _bgl_GCtrick else _vcf
        markers_file = _markers_GCtrick_refined if _markers_GCtrick_refined else _vcf
        
        # Extract java path and jar path from the beagle command
        # Expected format: "java -jar beagle.jar" -> split into java_path and jar_path
        parts = _beagle.split()
        if len(parts) >= 3 and parts[1] == '-jar':
            java_path = parts[0]
            jar_path = parts[2]
            command = \
                "{java} -Xmx{java_mem} -jar {jar} unphased={vcf} markers={markers} out={vcf_phased} missing={missing}" \
                .format(java=java_path, java_mem=java_mem_formatted, jar=jar_path, vcf=unphased_file, markers=markers_file, vcf_phased=_vcf_phased, missing=_missing)
        else:
            # Fallback: assume it's already a java command
            command = \
                "{beagle} -Xmx{java_mem} unphased={vcf} markers={markers} out={vcf_phased} missing={missing}" \
                .format(beagle=_beagle, java_mem=java_mem_formatted, vcf=unphased_file, markers=markers_file, vcf_phased=_vcf_phased, missing=_missing)
        
    else:
        # BEAGLE 5.x uses: gt=, out=, nthreads=
        command = \
            "{beagle} -Xmx{java_mem} gt={vcf} out={vcf_phased} nthreads={nthreads}" \
            .format(beagle=_beagle, java_mem=java_mem_formatted, vcf=_vcf, vcf_phased=_vcf_phased, nthreads=_nthreads)

    
    Bash_BEAGLE_Phase(command, _vcf_phased)

    _vcf_phased = _out_prefix + '.vcf.gz'

    return _vcf_phased



def VCF2BEAGLE(_vcf_phased, _out_prefix, _vcf2beagle, _java=which("java"), _java_mem='1G', _f_save_intermediates=False):
    """
    Phased VCF(ex. *.vcf.gz) to Beagle(v3.x) file Conversion.
    """

    command1 = "gunzip -c {}".format(_vcf_phased)
    # print(command1)
    sbp_gunzip = sbp.Popen(command1.split(), stdout=sbp.PIPE)

    # Convert memory format for Java commands (always use MB for jar files)
    java_mem_formatted = _convert_memory_format(_java_mem, _vcf2beagle)

    command2 = "{java} -Xmx{java_mem} -jar {vcf2beagle} {missing} {prefix}" \
        .format(java=_java, java_mem=java_mem_formatted, vcf2beagle=_vcf2beagle, missing='0', prefix=_out_prefix)
    # print(command2)
    try:
        with open(_out_prefix + '.bgl.gz.log', 'w') as f_log:
            sbp.run(command2.split(), stdin=sbp_gunzip.stdout, stdout=sbp.DEVNULL, stderr=f_log)

    except sbp.CalledProcessError:
        raise HATK_BEAGLE_Execution_Error("Next BEAGLE 'vcf2beagle.jar' execution failed. ('{}')".format(command2))
    else:
        if not _f_save_intermediates:
            os.remove(_out_prefix+'.bgl.gz.log')
            os.remove(_out_prefix+'.int')
            os.remove(_out_prefix+'.markers')

        return _out_prefix + '.bgl.gz'

    finally:
        sbp_gunzip.stdout.close()



def FixBglHeader(_bgl_gz, _out_gz):
    """
    Output from vcf2beagle.jar has the only "I id ..." header line.
    Thie function is to generate the complete header.
    """

    with gzip.open(_bgl_gz, 'rb') as f_bgl_gz, gzip.open(_out_gz, 'wb') as f_out_gz:

        line_1st = f_bgl_gz.readline().decode('UTF-8')
        # print(line_1st)
        l_line_1st = line_1st.split()

        header_1st = ' '.join(['P', 'pedigree'] + l_line_1st[2:]) + '\n'
        header_2nd = line_1st
        header_3rd = ' '.join(['PID', 'father'] + ['0']*(len(l_line_1st) - 2)) + '\n'
        header_4th = ' '.join(['MID', 'mother'] + ['0']*(len(l_line_1st) - 2)) + '\n'
        header_5th = ' '.join(['C', 'sex'] + ['0']*(len(l_line_1st) - 2)) + '\n'

        f_out_gz.write(header_1st.encode())
        f_out_gz.write(header_2nd.encode())
        f_out_gz.write(header_3rd.encode())
        f_out_gz.write(header_4th.encode())
        f_out_gz.write(header_5th.encode())
        f_out_gz.writelines(f_bgl_gz) # main GT content as it is.

    return _out_gz



unGCtrick = GCtricedBGL2OriginalBGL_2



def Phasing_wrapper(_bgl, _markers, _out_prefix, _beagle2vcf, _vcf2beagle, _beagle=which("beagle"),
                    _java=which("java"), _java_mem='1G', _nthreads=1, _f_save_intermediates=False, _f_gzip=True, _missing='0', beagle_version='3.3.2'):

    ### Main Variables ###
    _out_dir = dirname(_out_prefix)

    ### Main Actions ###
    print(std_MAIN + "Phasing.")

    ## GCtrick
    print("[1] GCtrick: ")
    _bgl_GCtrick, _markers_GCtrick_refined = GCtrick(_bgl, _markers, _out_dir, _f_save_intermediates)
    print("   - {}\n"
          "   - {}".format(_bgl_GCtrick, _markers_GCtrick_refined))

    ## beagle2vcf
    print("[2] beagle2vcf: ")
    _vcf_GCtrick = \
        BEAGLE2VCF(_bgl_GCtrick, _markers_GCtrick_refined, _out_prefix+'.vcf', _beagle2vcf, _java, _java_mem,
                   _f_save_intermediates, _f_gzip)
    print("   - {}".format(_vcf_GCtrick))

    ## Phase
    print("[3] beagle phasing: ")
    print("(It can take some time.)", end='\r')
    _vcf_phased = _out_prefix+'.phased'
    _vcf_phased = Beagle_Phase(_vcf_GCtrick, _vcf_phased, _bgl_GCtrick, _markers_GCtrick_refined, _beagle, _java_mem, _nthreads, _f_save_intermediates, _missing)
    print("   - {}".format(_vcf_phased))

    is_beagle_3 = (beagle_version == '3.3.2')

    if is_beagle_3:
        # For BEAGLE 3.3.2, skip vcf2beagle and FixBglHeader, use phased bgl from GCtrick step
        # BEAGLE 3.3.2 generates files with pattern: {out_prefix}.phased.{input_basename}.phased.gz
        bgl_input_basename = basename(_bgl_GCtrick)
        bgl_phased_gz = f"{_out_prefix}.phased.{bgl_input_basename}.phased.gz"
        print("[4] vcf2beagle: (skipped for BEAGLE 3.3.2)")
        print(f"   - {bgl_phased_gz}")

        print("[5] FixBglHeader: (skipped for BEAGLE 3.3.2)")

        print("[6] unGCtrick: ")
        __RETURN__ = _out_prefix + '.bgl.phased'
        __RETURN__ = unGCtrick(bgl_phased_gz, _markers, __RETURN__)
        print(f"   - {__RETURN__}\n")
    else:
        # For BEAGLE 5.x, continue as before
        print("[4] vcf2beagle: ")
        out_prefix_temp = _out_prefix+'.phased'
        _bgl_phased_gz0 = VCF2BEAGLE(_vcf_phased, out_prefix_temp, _vcf2beagle, _java, _java_mem)
        print("   - {}".format(_bgl_phased_gz0))

        print("[5] FixBglHeader: ")
        out_prefix_temp = _out_prefix+'.phased.bgl.header.GCtrick.gz'
        _bgl_phased_gz1 = FixBglHeader(_bgl_phased_gz0, out_prefix_temp)
        print("   - {}".format(_bgl_phased_gz1))

        print("[6] unGCtrick: ")
        __RETURN__ = _out_prefix+'.bgl.phased'
        __RETURN__ = unGCtrick(_bgl_phased_gz1, _markers, __RETURN__)
        print("   - {}\n".format(__RETURN__))

    if not _f_save_intermediates:
        ## GCtrick
        os.remove(_bgl_GCtrick)
        os.remove(_markers_GCtrick_refined)

        ## beagle2vcf
        os.remove(_vcf_GCtrick)

        ## Phase
        # os.remove(_vcf_phased)

        # Remove intermediate files for BEAGLE 3.3.2
        if is_beagle_3:
            ## Remove phased bgl gz and related files if needed
            if os.path.exists(bgl_phased_gz):
                os.remove(bgl_phased_gz)
            # Remove BEAGLE 3.3.2 auxiliary outputs
            for ext in ["dose.gz", "gprobs.gz", "r2"]:
                aux_file = bgl_phased_gz.replace(".phased.gz", f".{ext}")
                if os.path.exists(aux_file):
                    os.remove(aux_file)
        else:
            # Remove intermediate files for BEAGLE 5.x
            ## vcf2beagle
            os.remove(_bgl_phased_gz0)
            ## FixBglHeader
            os.remove(_bgl_phased_gz1)

    return __RETURN__



if __name__ == '__main__':

    ## GCtrick
    # bgl = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.bgl"
    # markers = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.markers"
    # out_dir = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE"
    # GCtrick(bgl, markers, out_dir)

    ## beagle2vcf
    # bgl_GCtrick = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.bgl.GCtrick"
    # markers_GCtrick_refined = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.markers.GCtrick.refined"
    # out = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.vcf"
    # beagle2vcf = "/home/wansonchoi/sf_VirtualBox_Share/HATK/dependency/beagle2vcf.jar"
    # BEAGLE2VCF(bgl_GCtrick, markers_GCtrick_refined, out, beagle2vcf)

    ## Phase
    # vcf = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.vcf.gz"
    # out = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.phased"
    # Beagle_Phase(vcf, out, _nthreads=4, _java_mem='4G')

    ## vcf2beagle
    # vcf_phased = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/remove/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.phased.vcf.gz"
    # out = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/remove/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.phased"
    # vcf2beagle = "/home/wansonchoi/sf_VirtualBox_Share/HATK/dependency/vcf2beagle.jar"
    # VCF2BEAGLE(vcf_phased, out, vcf2beagle)

    ## FixBglHeader
    # bgl_gz = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/remove/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.phased.bgl.gz"
    # out_gz = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/remove/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.phased.bgl.header.GCtrick.gz"
    # FixBglHeader(bgl_gz, out_gz)

    ## unGCtrick
    # bgl_phased_gz = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/remove/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.phased.bgl.header.GCtrick.gz"
    # markers = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/remove/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.markers.refined"
    # out = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/remove/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.tt.bgl.phased"
    # unGCtrick(bgl_phased_gz, markers, out)


    ## whole implementation
    bgl = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.chr6.hg18.29-34mb.bgl"
    markers = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.chr6.hg18.29-34mb.markers"
    out_prefix = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/20220314_BEAGLE/wtccc_filtered_58C_RA.hatk.300+300.imgt3470.header.subset.chr6.hg18.29-34mb"
    beagle2vcf = "/home/wansonchoi/sf_VirtualBox_Share/HATK/dependency/beagle2vcf.jar"
    vcf2beagle = "/home/wansonchoi/sf_VirtualBox_Share/HATK/dependency/vcf2beagle.jar"

    r = Phasing_wrapper(bgl, markers, out_prefix, beagle2vcf, vcf2beagle, _java_mem='4G', _nthreads=4)
    print("Phased: {}".format(r))

    pass