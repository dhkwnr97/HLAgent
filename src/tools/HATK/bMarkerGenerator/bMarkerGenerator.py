# -*- coding: utf-8 -*-

import os, sys, re
from os.path import basename, dirname, join

from .src.encodeVariants import encodeVariants
from .src.encodeHLA import encodeHLA
from .src.HLAtoSequences import HLAtoSequences
from src.tools.HATK.src.PLINK_Bash import Bash_RUN_PLINK
from src.tools.HATK.NomenCleaner.src.CHPED import CHPED
from .bMarker import bMarker

std_MAIN_PROCESS_NAME = "\n[%s]: " % basename(__file__)
std_ERROR_MAIN_PROCESS_NAME = "\n[%s::ERROR]: " % basename(__file__)
std_WARNING_MAIN_PROCESS_NAME = "\n[%s::WARNING]: " % basename(__file__)


def bMarkerGenerator(_CHPED:CHPED, _out, _hg,
                     _dictionary_AA_seq, _dictionary_AA_map, _dictionary_SNPS_seq, _dictionary_SNPS_map,
                     _variants=None, _f_save_intermediates=False,
                     _plink=None, _config=None):

    ### Main Variables ###
    _out_dir = dirname(_out)
    
    # Load configuration parameters with defaults
    config = _config or {}
    
    # Binary marker settings (which marker types to include)
    binary_settings = config.get('_binary_marker_settings', {})
    include_hla_alleles = binary_settings.get('include_hla_alleles', True)
    include_aa_residues = binary_settings.get('include_aa_residues', True)
    include_intragenic_snps = binary_settings.get('include_intragenic_snps', True)
    include_intergenic_snps = binary_settings.get('include_intergenic_snps', True)
    
    # QC parameters with defaults
    qc_params = config.get('_qc_parameters', {})
    mind_threshold = qc_params.get('mind', 0.3)
    geno_threshold = qc_params.get('geno', 0.5)
    maf_threshold = qc_params.get('maf_threshold', 0.0001)
    hwe_threshold = qc_params.get('hwe_threshold', 0.000001)
    
    # Processing stages (which processing steps to execute)
    stages = config.get('_stages', {})
    enable_qc_filtering = stages.get('enable_qc_filtering', True)
    enable_founder_extraction = stages.get('enable_founder_extraction', True)
    enable_merging = stages.get('enable_merging', True)
    
    # Performance and logging settings
    performance = config.get('_performance', {})
    show_progress = performance.get('show_progress', True)
    
    # Validation settings
    validation = config.get('_validation', {})
    check_marker_compatibility = validation.get('check_marker_compatibility', True)

    # _dictionary_AA_seq = _dictionary_AA + ".txt" # From now on, official extension of HLA sequence information dictionary is ".txt". (2018. 9. 25.)
    # _dictionary_AA_map = _dictionary_AA + ".map"
    #
    # _dictionary_SNPS_seq = _dictionary_SNPS + ".txt"
    # _dictionary_SNPS_map = _dictionary_SNPS + ".map"

    _variants2 = join(_out_dir, basename(_variants)) if _variants else None

    __SNP__ = None
    __HLA__ = None
    __AA__ = None
    __SNPS__ = None
    __MERGED__ = None

    plink = "{} --noweb --silent --allow-no-sex --keep-allele-order".format(_plink) # plink = ' '.join([_plink, "--noweb", "--silent"]) - previously (2022.03.02.)



    ### Main Actions ###

    ########## <Making Reference Panel> ##########
    if show_progress:
        print(std_MAIN_PROCESS_NAME + "Making Reference Panel for \"{0}\"\n".format(_out))
        if not include_hla_alleles:
            print("[INFO] HLA allele markers disabled by configuration")
        if not include_aa_residues:
            print("[INFO] Amino acid residue markers disabled by configuration")
        if not include_intragenic_snps:
            print("[INFO] Intragenic SNP markers disabled by configuration")
        if not include_intergenic_snps:
            print("[INFO] Intergenic SNP markers disabled by configuration")

    # Generate marker types based on configuration
    __AA__ = ENCODE_AA(_CHPED, _dictionary_AA_seq, _dictionary_AA_map, _out, _out_dir, plink, _f_save_intermediates) if include_aa_residues else None  # _out+'.AA.CODED'
    __HLA__ = ENCODE_HLA(_CHPED, _hg, _out, plink, _f_save_intermediates) if include_hla_alleles else None  # _out+'.HLA'
    __SNPS__ = ENCODE_SNPS(_CHPED, _dictionary_SNPS_seq, _dictionary_SNPS_map, _out, _out_dir, plink, _f_save_intermediates) if include_intragenic_snps else None  # _out+'.SNPS.CODED'

    # Hadr-coding for test.
    # __AA__ = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/HATK_rearchitect_bMG_20220301/wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.bmarker.AA.CODED"
    # __HLA__ = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/HATK_rearchitect_bMG_20220301/wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.bmarker.HLA"
    # __SNPS__ = "/home/wansonchoi/sf_VirtualBox_Share/HATK/tests/HATK_rearchitect_bMG_20220301/wtccc_filtered_58C_RA.hatk.300+300.chr6.hg18.bmarker.SNPS.CODED"

    # Above 3 code blocks are implmented no matter `_variants`(Normal genomewide SNPs) is given or not.
    # Next parts are implented sligtly differently depending on `_variants`.


    if enable_founder_extraction and show_progress:
        print("[6] Extracting founders.")
    
    # Extract founders only for enabled marker types
    __SNP__ = None
    if enable_founder_extraction:
        __SNP__ = EXTRACT_FOUNDERS(_variants, _variants2, _out_dir, "SNP", plink, _f_save_intermediates, maf_threshold) if (_variants and include_intergenic_snps) else None
        __AA__ = EXTRACT_FOUNDERS(__AA__, _out, _out_dir, "AA", plink, _f_save_intermediates, maf_threshold) if __AA__ else None
        __HLA__ = EXTRACT_FOUNDERS(__HLA__, _out, _out_dir, "HLA", plink, _f_save_intermediates, maf_threshold) if __HLA__ else None
        __SNPS__ = EXTRACT_FOUNDERS(__SNPS__, _out, _out_dir, "SNPS", plink, _f_save_intermediates, maf_threshold) if __SNPS__ else None
    else:
        # Skip founder extraction if disabled
        __AA__ = __AA__ if __AA__ else None
        __HLA__ = __HLA__ if __HLA__ else None 
        __SNPS__ = __SNPS__ if __SNPS__ else None

    if enable_merging and show_progress:
        print("[7] Merging SNP, HLA, and amino acid datasets.")
    
    # Merge only enabled marker types
    if enable_merging:
        # Filter out None values for disabled marker types
        marker_files = [f for f in [__SNP__, __AA__, __HLA__, __SNPS__] if f is not None]
        if not marker_files:
            raise ValueError("No marker types enabled - at least one marker type must be included")
        __MERGED__ = MERGE(__SNP__, __AA__, __HLA__, __SNPS__, _out, _out_dir, plink, _f_save_intermediates)
    else:
        # If merging is disabled, use the last available marker type as output
        marker_files = [f for f in [__SNPS__, __HLA__, __AA__, __SNP__] if f is not None]
        if not marker_files:
            raise ValueError("No marker types enabled - at least one marker type must be included")
        __MERGED__ = marker_files[0]  # Use first available marker type

    if enable_qc_filtering and show_progress:
        print("[8] Performing quality control.")
    
    # Apply QC with configurable parameters
    if enable_qc_filtering:
        __RETURN__ = QC(__MERGED__, _out, _out_dir, plink, _f_save_intermediates, 
                       geno_threshold=geno_threshold, maf_threshold=maf_threshold, 
                       hwe_threshold=hwe_threshold)
    else:
        # Skip QC if disabled, just copy the merged file to final output
        if show_progress:
            print("[8] Skipping quality control (disabled by configuration).")
        import shutil
        for ext in ['.bed', '.bim', '.fam']:
            shutil.copy2(__MERGED__ + ext, _out + ext)
        __RETURN__ = _out

    if show_progress:
        # Create completion message based on enabled marker types
        enabled_types = []
        if include_hla_alleles: enabled_types.append("HLA")
        if include_aa_residues: enabled_types.append("AA")
        if include_intragenic_snps: enabled_types.append("SNPS")
        if include_intergenic_snps and _variants: enabled_types.append("SNPs")
        
        completion_msg = "[9] Making reference panel for {} is Done!".format(
            ", ".join(enabled_types) if enabled_types else "no marker types (check configuration)"
        )
        print(completion_msg)

    # Pass configuration to bMarker for enhanced functionality
    return bMarker(__RETURN__, _f_save_intermediates)



def ENCODE_AA(_CHPED: CHPED, _dictionary_AA_seq, _dictionary_AA_map, _out, _out_dir, plink, _f_save_intermediates):
    """
    Encode amino acid sequences from HLA types.
    This generates binary markers for amino acid residue positions.
    """
    '''
    echo "[$i] Generating amino acid sequences from HLA types.";  @ i++
    ./HLAtoSequences.pl $_chped HLA_DICTIONARY_AA.txt AA > $OUTPUT.AA.ped
    cp HLA_DICTIONARY_AA_hg19.map $OUTPUT.AA.map # hg19
    # cp HLA_DICTIONARY_AA.map $OUTPUT.AA.map

    echo "[$i] Encoding amino acids positions." ;  @ i++
    ./encodeVariants.pl $OUTPUT.AA.ped $OUTPUT.AA.map $OUTPUT.AA.CODED

    plink --file $OUTPUT.AA.CODED --missing-genotype 0 --make-bed --out $OUTPUT.AA.TMP
    awk '{if ($5 == "0" || $5 == "x" || $6 == "x"){print $2}}' $OUTPUT.AA.TMP.bim | grep -v INS | cut -f2 > to_remove
    plink --bfile $OUTPUT.AA.TMP --exclude to_remove --make-bed --out $OUTPUT.AA.CODED

    # rm $OUTPUT.AA.TMP*; rm to_remove
    # rm $OUTPUT.AA.???
    '''

    print("[1] Generating Amino acid(AA)sequences from HLA types.")
    ### (1) Sequence File ( *.AA.{ped,map} ) ###
    HLAtoSequences(_CHPED.chped, _dictionary_AA_seq, "AA", _out, _f_hasHeader=_CHPED.f_hasHeader,
                   _HLA_target=_CHPED.HLA_avail)
    os.system(' '.join(["cp", _dictionary_AA_map, _out + '.AA.map']))


    print("[2] Encoding Amino acids positions.")
    ### (2) pre-CODED File ( *.AA.CODED.{ped,map},  *.AA.CODED.factors ) ###
    encodeVariants(_out + '.AA.ped', _out + '.AA.map', _out + '.AA.CODED')  # previously "enCODED".


    ### (3) stuffs to remove ( *.AA.TMP.{bed,bim,fam}, to_remove ) ###
    command = ' '.join([plink, "--make-bed", "--file", _out+'.AA.CODED', "--missing-genotype 0", "--out", _out+'.AA.TMP'])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, _out + '.AA.TMP', _f_save_intermediates)

    command = ' '.join(
        ["awk", '\'{if ($5 == "0" || $5 == "x" || $6 == "x"){print $2}}\'', _out+'.AA.TMP.bim', "|",
         "cut -f2", ">", join(_out_dir, "to_remove")])

    """
    In the previous framework which was created by Sherman Jia, The insertions were dealt as a marker "INS".
    In the new version of Framework, marker label is "INDEL".
    """

    # print(command)
    os.system(command)

    ### (4) Final Encoded outputs ( *.AA.CODED.{bed,bim,fam,nosex,log} ) ###
    command = ' '.join(
        [plink, "--make-bed", "--bfile", _out+'.AA.TMP', "--exclude", join(_out_dir, "to_remove"), "--out", _out+'.AA.CODED'])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, _out + '.AA.CODED', _f_save_intermediates)

    """
    Generated outputs :
        (1) Sequence File ( *.AA.{ped,map} )
        (2) pre-CODED File ( *.AA.CODED.{ped,map}, *.AA.CODED.factors )
        (3) stuffs to remove ( *.AA.TMP.{bed,bim,fam}, to_remove )
        (4) Final Encoded outputs ( *.AA.CODED.{bed,bim,fam,nosex,log}


    Final outputs :
        - *.AA.CODED.{bed,bim,fam,factors,nosex,log}

    Outputs to remove :
        - *.AA.{ped,map}
        - *.AA.TMP.*
        - to_remove
        - *.AA.CODED.{ped,map}

    """

    if not _f_save_intermediates:
        os.remove(_out+".AA.ped")
        os.remove(_out+".AA.map")
        os.remove(_out+".AA.TMP.bed")
        os.remove(_out+".AA.TMP.bim")
        os.remove(_out+".AA.TMP.fam")
        os.remove(join(_out_dir, "to_remove"))
        os.remove(_out+".AA.CODED.ped")
        os.remove(_out+".AA.CODED.map")
        os.remove(_out+".AA.CODED.factors")


    return _out + '.AA.CODED'


def ENCODE_HLA(_CHPED: CHPED, _hg, _out, plink, _f_save_intermediates):
    """
    Encode HLA alleles as binary markers.
    This generates binary markers for HLA allele presence/absence.
    """

    print("[3] Encoding HLA alleles.")

    ### (1) Encoded HLA ( *.HLA.{ped,map} ) ###
    encodeHLA(_CHPED.chped, _out + ".HLA", _hg, _f_hasHeader=_CHPED.f_hasHeader,
              _HLA_target=_CHPED.HLA_avail)

    ### (2) Final Encoded Outputs ( *.HLA.{bed,bim,fam,nosex,log} ) ###
    command = ' '.join([plink, "--make-bed", "--file", _out + '.HLA', "--out", _out + '.HLA'])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, _out + '.HLA', _f_save_intermediates)

    """
    Generaed outputs :
        (1) Encoded HLA ( *.HLA.{ped,map} )
        (2) Final Encoded Outputs ( *.HLA.{bed,bim,fam}, *.HLA.{nosex,log} )

    Final outputs :
        - *.HLA.{bed,bim,fam,factors,nosex,log}

    Outputs to remove :
        - *.HLA.{ped,map}
    """

    if not _f_save_intermediates:
        os.remove(_out+".HLA.ped")
        os.remove(_out+".HLA.map")

    return _out+'.HLA'


def ENCODE_SNPS(_CHPED: CHPED, _dictionary_SNPS_seq, _dictionary_SNPS_map, _out, _out_dir, plink, _f_save_intermediates):
    """
    Encode intragenic SNP sequences from HLA types.
    This generates binary markers for SNP positions within HLA genes.
    """

    print("[4] Generating DNA(SNPS) sequences from HLA types.")

    ### (1) Sequence File ( *.SNPS.{ped,map} )
    HLAtoSequences(_CHPED.chped, _dictionary_SNPS_seq, "SNPS", _out, _f_hasHeader=_CHPED.f_hasHeader,
                   _HLA_target=_CHPED.HLA_avail)

    command = ' '.join(["cp", _dictionary_SNPS_map, _out + '.SNPS.map'])
    # print(command)
    os.system(command)


    print("[5] Encoding SNP positions.")

    ### (2) pre-CODED File ( *.SNPS.CODED.{ped,map} )
    encodeVariants(_out + '.SNPS.ped', _out + '.SNPS.map', _out + '.SNPS.CODED')


    ### (3) Stuffs to remove ( *.SNPS.TMP.{bed,bim,fam}, to_remove )
    command = ' '.join(
        [plink, "--make-bed", "--file", _out + '.SNPS.CODED', "--missing-genotype 0", "--out", _out + '.SNPS.TMP'])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, _out + '.SNPS.TMP', _f_save_intermediates)

    command = ' '.join(
        ["awk", '\'{if ($5 == "0" || $5 == "x" || $6 == "x"){print $2}}\'', _out + '.SNPS.TMP.bim', "|",
         "cut -f2", ">", join(_out_dir, "to_remove")])
    # print(command)
    os.system(command)

    ### (4) Final Encoded outputs ( *.SNPS.CODED.{bed,bim,fam,nosex,log} )
    command = ' '.join(
        [plink, "--make-bed", "--bfile", _out + '.SNPS.TMP', "--exclude", join(_out_dir, "to_remove"), "--out", _out + '.SNPS.CODED'])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, _out + '.SNPS.CODED', _f_save_intermediates)

    """
    Generated outputs :
        (1) Sequence File ( *.SNPS.{ped,map} )
        (2) pre-CODED File ( *.SNPS.CODED.{ped,map}, *.SNPS.CODED.factors )
        (3) stuffs to remove ( *.SNPS.TMP.{bed,bim,fam}, to_remove )
        (4) Final Encoded outputs ( *.SNPS.CODED.{bed,bim,fam,nosex,log}


    Final outputs :
        - *.SNPS.CODED.{bed,bim,fam,factors,nosex,log}

    Outputs to remove :
        - *.SNPS.{ped,map}
        - *.SNPS.TMP.*
        - to_remove
        - *.SNPS.CODED.{ped,map}

    """

    if not _f_save_intermediates:
        os.remove(_out + ".SNPS.ped")
        os.remove(_out + ".SNPS.map")
        os.remove(_out + ".SNPS.TMP.bed")
        os.remove(_out + ".SNPS.TMP.bim")
        os.remove(_out + ".SNPS.TMP.fam")
        os.remove(join(_out_dir, "to_remove"))
        os.remove(_out + ".SNPS.CODED.ped")
        os.remove(_out + ".SNPS.CODED.map")
        os.remove(_out + ".SNPS.CODED.factors")


    return _out + '.SNPS.CODED'


def EXTRACT_FOUNDERS(_bfile, _out, _out_dir, _type, plink, _f_save_intermediates, _maf=0.0001):

    """
    Generated outputs :
        (1) --filter-founders to variants data ( *.FOUNDERS )
        (2) QC ( *.FOUNDERS.{hardy,freq,missing )
        (3) Stuffs to remove ( remove.snps.hardy, remove.snps.freq, remove.snps.missing, all.remove.snps )
        (4) Filtering out Quality-controled FOUNDERS ( *.FOUNDERS.QC )
        (5) --filter-founders to HLA information ( *.{HLA,AA,SNPS}.FOUNDERS )

    Final outputs :
        - *.FOUNDERS.QC
        - *.{HLA,AA,SNPS}.FOUNDERS

    Outputs to remove :
        - *.FOUNDERS
        - *.FOUNDERS.{hardy,freq,missing}
        - remove.snps.hardy, remove.snps.freq, remove.snps.missing, all.remove.snps

    """

    if _type not in ("SNP", "AA", "HLA", "SNPS"): return None


    if _type == "SNP":
        """
        if ($EXTRACT_FOUNDERS) then
            echo "[$i] Extracting founders."; @ i++
            plink --bfile $_variants --filter-founders --mind 0.3 --alleleACGT --make-bed --out $_variants.FOUNDERS

            # Initial QC on Reference SNP panel
            plink --bfile $_variants.FOUNDERS --hardy        --out $_variants.FOUNDERS.hardy  # 진짜 92명에 대해 position별로 HWE test한 결과
            plink --bfile $_variants.FOUNDERS --freq         --out $_variants.FOUNDERS.freq   # 실제 --freq 옵션이 allele frequency계산해주는 옵션임. 
            plink --bfile $_variants.FOUNDERS --missing      --out $_variants.FOUNDERS.missing
            awk '{if (NR > 1){print}}' $_variants.FOUNDERS.hardy.hwe      | awk ' $9 < 0.000001 { print $2 }' | sort -u > remove.snps.hardy 
            awk '{if (NR > 1){print}}' $_variants.FOUNDERS.freq.frq       | awk ' $5 < 0.01 { print $2 } '             > remove.snps.freq
            awk '{if (NR > 1){print}}' $_variants.FOUNDERS.missing.lmiss  | awk ' $5 > 0.05 { print $2 } '              > remove.snps.missing
            cat remove.snps.*                                            | sort -u                                     > all.remove.snps

            plink --bfile $_variants.FOUNDERS --allow-no-sex --exclude all.remove.snps --make-bed --out $_variants.FOUNDERS.QC

            # Founders are identified here as individuals with "0"s in mother and father IDs in .fam file

            plink --bfile $OUTPUT.HLA --filter-founders --maf 0.0001 --make-bed --out $OUTPUT.HLA.FOUNDERS
            plink --bfile $OUTPUT.SNPS.CODED --filter-founders --maf 0.0001 --make-bed --out $OUTPUT.SNPS.FOUNDERS
            plink --bfile $OUTPUT.AA.CODED --filter-founders --maf 0.0001 --make-bed --out $OUTPUT.AA.FOUNDERS

            rm remove.snps.*
        endif
        """

        ### (1) --filter-founders to variants data ( *.FOUNDERS )
        command = ' '.join([plink, "--make-bed",
                            "--bfile", _bfile,
                            "--filter-founders",
                            "--mind 0.3",  # Keep mind threshold at 0.3 for SNPs
                            "--alleleACGT",
                            "--out", _out + '.FOUNDERS'])
        # print(command)
        # os.system(command)
        Bash_RUN_PLINK(command, _out + '.FOUNDERS', _f_save_intermediates)

        ### (2) QC ( *.FOUNDERS.{hardy,freq,missing )
        # Initial QC on Reference SNP panel
        command = ' '.join([plink, "--bfile", _out + '.FOUNDERS', "--hardy", "--out", _out + '.FOUNDERS.hardy'])
        # print(command)
        # os.system(command)
        Bash_RUN_PLINK(command, _out + '.FOUNDERS.hardy', _f_save_intermediates)
        command = ' '.join([plink, "--bfile", _out + '.FOUNDERS', "--freq", "--out", _out + '.FOUNDERS.freq'])
        # print(command)
        # os.system(command)
        Bash_RUN_PLINK(command, _out + '.FOUNDERS.freq', _f_save_intermediates)
        command = ' '.join([plink, "--bfile", _out + '.FOUNDERS', "--missing", "--out", _out + '.FOUNDERS.missing'])
        # print(command)
        # os.system(command)
        Bash_RUN_PLINK(command, _out + '.FOUNDERS.missing', _f_save_intermediates)

        ### (3) Stuffs to remove ( remove.snps.hardy, remove.snps.freq, remove.snps.missing, all.remove.snps )
        # Use configurable thresholds - these will be passed from main function
        hwe_thresh = 0.000001  # Default HWE threshold
        freq_thresh = 0.01     # Default frequency threshold  
        missing_thresh = 0.05  # Default missing threshold
        
        command = ' '.join(["awk", "'{if (NR > 1){print}}'", _out + '.FOUNDERS.hardy.hwe', "|",
                            "awk", "' $9 < {} {{ print $2 }}'".format(hwe_thresh), "|", "sort -u", ">", join(_out_dir, "remove.snps.hardy")])
        # print(command)
        os.system(command)
        command = ' '.join(["awk", "'{if (NR > 1){print}}'", _out + '.FOUNDERS.freq.frq', "|",
                            "awk", "' $5 < {} {{ print $2 }} '".format(freq_thresh), ">", join(_out_dir, "remove.snps.freq")])
        # print(command)
        os.system(command)
        command = ' '.join(["awk", "'{if (NR > 1){print}}'", _out + '.FOUNDERS.missing.lmiss', "|",
                            "awk", "' $5 > {} {{ print $2 }} '".format(missing_thresh), ">", join(_out_dir, "remove.snps.missing")])
        # print(command)
        os.system(command)
        command = ' '.join(["cat", join(_out_dir, "remove.snps.hardy"), join(_out_dir, "remove.snps.freq"), join(_out_dir, "remove.snps.missing"), "|",
                            "sort -u", ">", join(_out_dir, "all.remove.snps")])
        # print(command)
        os.system(command)

        ### (4) Filtering out Quality-controled FOUNDERS ( *.FOUNDERS.QC )
        __SNP__ = _out + '.FOUNDERS.QC'
        command = ' '.join([plink, "--make-bed",
                            "--bfile", _out + '.FOUNDERS',
                            "--exclude", join(_out_dir, "all.remove.snps"),
                            "--out", __SNP__])
        # print(command)
        # os.system(command)
        Bash_RUN_PLINK(command, __SNP__, _f_save_intermediates)

        # Founders are identified here as individuals with "0"s in mother and father IDs in .fam file

        if not _f_save_intermediates:
            os.remove(_out + ".FOUNDERS.bed")
            os.remove(_out + ".FOUNDERS.bim")
            os.remove(_out + ".FOUNDERS.fam")

            os.remove(_out + ".FOUNDERS.hardy.hwe")
            os.remove(_out + ".FOUNDERS.freq.frq")
            os.remove(_out + ".FOUNDERS.missing.imiss")
            os.remove(_out + ".FOUNDERS.missing.lmiss")

            os.remove(join(_out_dir, "remove.snps.hardy"))
            os.remove(join(_out_dir, "remove.snps.freq"))
            os.remove(join(_out_dir, "remove.snps.missing"))
            os.remove(join(_out_dir, "all.remove.snps"))


        return __SNP__

    else:
        ### (5) --filter-founders to HLA information ( *.{HLA,AA,SNPS}.FOUNDERS )
        __TMP__ = _out+'.{type}.FOUNDERS'.format(type=_type)
        maf_option = "--maf {}".format(_maf) if _maf > 0 else "--maf 0.0001"  # Use configurable MAF threshold
        command = ' '.join([plink, "--make-bed",
                            "--bfile", _bfile,
                            "--filter-founders",
                            maf_option,
                            "--out", __TMP__])
        # print(command)
        # os.system(command)
        Bash_RUN_PLINK(command, __TMP__, _f_save_intermediates)

        if not _f_save_intermediates:
            os.remove(_bfile+'.bed')
            os.remove(_bfile+'.bim')
            os.remove(_bfile+'.fam')

        return __TMP__


def MERGE(__SNP__, __AA__, __HLA__, __SNPS__, _out, _out_dir, plink, _f_save_intermediates):

    """
    Generated Outputs :
        (1) Stuffs to merge ( merge_list )
        (2) Merging the above stuffs ( *.MERGED.FOUNDERS )

    Final outputs :
        - *.MERGED.FOUNDERS

    Outputs to remove :
        - *.{AA,HLA,SNPS}.FOUNDERS.{bed,bim,fam}
        - merge_list

    """

    ### (1) Collect available marker files for merging
    TMP_merged_list = join(_out_dir, "merge_list")
    
    # Collect non-None marker files
    marker_files = []
    marker_names = []
    
    if __HLA__:
        marker_files.append(__HLA__)
        marker_names.append("HLA")
    if __AA__:
        marker_files.append(__AA__)
        marker_names.append("AA")
    if __SNPS__:
        marker_files.append(__SNPS__)
        marker_names.append("SNPS")
    if __SNP__:
        marker_files.append(__SNP__)
        marker_names.append("SNP")
    
    if not marker_files:
        raise ValueError("No marker files available for merging - all marker types are disabled or failed")
    
    if len(marker_files) == 1:
        # If only one marker file, no need to merge - just copy it to the output
        single_file = marker_files[0]
        __MERGED__ = _out + '.MERGED.FOUNDERS'
        
        import shutil
        for ext in ['.bed', '.bim', '.fam']:
            shutil.copy2(single_file + ext, __MERGED__ + ext)
        
        print(f"[INFO] Only one marker type ({marker_names[0]}) available - skipping merge step")
        return __MERGED__
    
    ### (2) Create merge list with available files
    print(f"[INFO] Merging {len(marker_files)} marker types: {', '.join(marker_names)}")
    
    # Write the first file to start the merge list
    with open(TMP_merged_list, 'w') as f:
        for i, marker_file in enumerate(marker_files):
            f.write(f"{marker_file}.bed {marker_file}.bim {marker_file}.fam\n")

    ### (3) Merging the above stuffs ( *.MERGED.FOUNDERS )
    __MERGED__ = _out + '.MERGED.FOUNDERS'
    command = ' '.join([plink, "--make-bed", "--merge-list", TMP_merged_list, "--out", __MERGED__])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, __MERGED__, _f_save_intermediates)

    ### (4) Cleanup intermediate files
    if not _f_save_intermediates:
        for marker_file in marker_files:
            if marker_file:  # Double check for None
                for ext in ['.bed', '.bim', '.fam']:
                    try:
                        os.remove(marker_file + ext)
                    except FileNotFoundError:
                        pass  # File may not exist, continue cleanup
        
        try:
            os.remove(TMP_merged_list)
        except FileNotFoundError:
            pass

    return __MERGED__


def QC(__MERGED__, _out, _out_dir, plink, _f_save_intermediates, 
       geno_threshold=0.5, maf_threshold=0.0001, hwe_threshold=0.000001):
    """
    Generated Outputs :
        (1) Frequency file to use in filtering out some snps ( *.MERGED.FOUNDERS.FRQ )
        (2) List up SNPs which have extreme allele frequency. ( all.remove.snps )
        (3) Making reference allele ( allele.order )
        (4) Filtering out SNPs which have extreme allele frequency(The reference panel for association test.) ( *.{bed,bim,fam} )
        (5) Allele frequency info. of output reference panel ( *.FRQ )

    Final outputs :
        - *.{bed,bim,fam}
        - *.FRQ

    Outputs to remove :
        - *.MERGED.FOUNDERS.FRQ
        - all.remove.snps
        - allele.order
        - TMP_allele_order (:= OUTPUT + ".refallele")
        - OUTPUT.{nosex,log}
        - *.FRQ.{nosex,log}

    """
    """
    plink --bfile $OUTPUT.MERGED.FOUNDERS --freq --out $OUTPUT.MERGED.FOUNDERS.FRQ
    awk '{if (NR > 1 && ($5 < 0.0001 || $5 > 0.9999)){print $2}}' $OUTPUT.MERGED.FOUNDERS.FRQ.frq > all.remove.snps
    awk '{if (NR > 1){if (($3 == "A" && $4 == "P") || ($4 == "A" && $3 == "P")){print $2 "\tP"}}}' $OUTPUT.MERGED.FOUNDERS.FRQ.frq > allele.order

    # QC: Maximum per-SNP missing > 0.5, MAF > 0.1%
    plink --bfile $OUTPUT.MERGED.FOUNDERS --reference-allele allele.order --exclude all.remove.snps --geno 0.5 --make-bed --out $OUTPUT

    # Calculate allele frequencies
    plink --bfile $OUTPUT --keep-allele-order --freq --out $OUTPUT.FRQ
    rm $_variants.FOUNDERS.*
    rm $OUTPUT.MERGED.FOUNDERS.*
    rm $OUTPUT.*.FOUNDERS.???
    rm allele.order
    rm all.remove.snps

    """

    # __MERGED__ == '_out + '.MERGED.FOUNDERS'

    TMP_all_remove_snps = join(_out_dir, "all.remove.snps")
    # TMP_allele_order = os.path.join(_out_dir, "allele.order")
    TMP_allele_order = _out + ".refallele"

    ### (1) Frequency file to use in filtering out some snps ( *.MERGED.FOUNDERS.FRQ )
    command = ' '.join([plink, "--freq", "--bfile", _out + '.MERGED.FOUNDERS', "--out", _out + '.MERGED.FOUNDERS.FRQ'])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, _out + '.MERGED.FOUNDERS.FRQ', _f_save_intermediates)

    ### (2) List up SNPs which have extreme allele frequency. ( all.remove.snps )
    # Use configurable MAF threshold
    max_freq = 1.0 - maf_threshold  # Calculate upper frequency threshold
    command = ' '.join(["awk", "'{{if (NR > 1 && ($5 < {} || $5 > {})){{print $2}}}}'".format(maf_threshold, max_freq),
                        _out + '.MERGED.FOUNDERS.FRQ.frq', ">", TMP_all_remove_snps])
    # print(command)
    os.system(command)

    ### (3) Making reference allele ( allele.order )
    # command = ' '.join(["awk", '\'{if (NR > 1){if (($3 == "A" && $4 == "P") || ($4 == "A" && $3 == "P")){print $2 "\tP"}}}\'', OUTPUT+'.MERGED.FOUNDERS.FRQ.frq', ">", TMP_allele_order])
    command = ' '.join(
        ["awk", '\'{if (NR > 1){if (($3 == "a" && $4 == "p") || ($4 == "a" && $3 == "p")){print $2 "\tp"}}}\'',
         _out + '.MERGED.FOUNDERS.FRQ.frq', ">", TMP_allele_order])
    # print(command)
    os.system(command)

    ### (4) Filtering out SNPs which have extreme allele frequency(The reference panel for association test.) ( *.{bed,bim,fam} )
    # QC: Use configurable thresholds
    command = ' '.join(
        [plink, "--make-bed", "--bfile", _out + '.MERGED.FOUNDERS', "--a1-allele", TMP_allele_order, "--exclude",
         TMP_all_remove_snps, "--geno {}".format(geno_threshold), "--out", _out])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, _out, _f_save_intermediates, _f_save_log=True)

    ### (5) Allele frequency info. of output reference panel ( *.FRQ )
    # Calculate allele frequencies
    command = ' '.join([plink, "--freq", "--bfile", _out, "--out", _out + '.FRQ'])
    # print(command)
    # os.system(command)
    Bash_RUN_PLINK(command, _out + '.FRQ', _f_save_intermediates, _f_save_log=True)


    if not _f_save_intermediates:

        os.remove(_out + ".MERGED.FOUNDERS.bed")
        os.remove(_out + ".MERGED.FOUNDERS.bim")
        os.remove(_out + ".MERGED.FOUNDERS.fam")
        os.remove(_out + ".MERGED.FOUNDERS.FRQ.frq")

        os.remove(TMP_all_remove_snps)
        os.remove(TMP_allele_order)

    # return _out+'.bed', _out+'.bim', _out+'.fam', _out+'.FRQ.frq'
    return _out

# if PREPARE:
#
#     print("[{}] Preparing files for Beagle.".format(index))
#
#     """
#     [Source from Buhm Han.]
#
#     awk '{print $2 " " $4 " " $5 " " $6}' $OUTPUT.bim > $OUTPUT.markers
#     plink --bfile $OUTPUT --keep-allele-order --recode --alleleACGT --out $OUTPUT
#     awk '{print "M " $2}' $OUTPUT.map > $OUTPUT.dat
#     cut -d ' ' -f1-5,7- $OUTPUT.ped > $OUTPUT.nopheno.ped
#
#     echo "[$i] Converting to beagle format.";  @ i++
#     linkage2beagle pedigree=$OUTPUT.nopheno.ped data=$OUTPUT.dat beagle=$OUTPUT.bgl standard=true > $OUTPUT.bgl.log
#
#
#     [Source from Yang.]
#
#     awk '{print $2 " " $4 " " $5 " " $6}' $OUTPUT.bim > $OUTPUT.markers
#     plink --bfile $OUTPUT --keep-allele-order --recode --alleleACGT --out $OUTPUT
#     plink --bfile $OUTPUT --recode --transpose --out $OUTPUT
#     # awk '{print "M " $2}' $OUTPUT.map > $OUTPUT.dat
#     # cut -d ' ' -f1-5,7- $OUTPUT.ped > $OUTPUT.nopheno.ped
#
#     echo "[$i] Converting to beagle format.";  @ i++
#     beagle2vcf -fnmarker $OUTPUT.markers -fnfam $OUTPUT.fam -fngtype $OUTPUT.tped -fnout $OUTPUT.vcf
#
#     I will make this code block based on source given by Yang. for now.
#
#     """
#
#
#     command = ' '.join(
#         ["awk", '\'{print $2 " " $4 " " $5 " " $6}\'', OUTPUT + '.bim', ">", OUTPUT + '.markers'])
#     print(command)
#     os.system(command)
#
#     command = ' '.join(
#         [plink, "--bfile", OUTPUT, "--keep-allele-order", "--recode", "--alleleACGT", "--out", OUTPUT])
#     print(command)
#     os.system(command)
#
#     command = ' '.join(["awk", '\'{print "M " $2}\'', OUTPUT + '.map', ">", OUTPUT + '.dat'])
#     print(command)
#     os.system(command)
#
#     command = ' '.join(["cut -d ' ' -f1-5,7-", OUTPUT + '.ped', ">", OUTPUT + '.nopheno.ped'])
#     print(command)
#     os.system(command)
#
#     index += 1
#
#     print("[{}] Converting to beagle format.".format(index))
#
#     command = ' '.join([linkage2beagle, "pedigree=" + OUTPUT + '.nopheno.ped', "data=" + OUTPUT + '.dat',
#                         "beagle=" + OUTPUT + '.bgl', "standard=true", ">", OUTPUT + '.bgl.log'])
#     print(command)
#     os.system(command)
#
#     index += 1
#
#
# if PHASE:
#
#     print("[{}] Phasing reference using Beagle (see progress in $OUTPUT.bgl.log).".format(index))
#
#     # Put this part postponed. (2017.11.29. by B. Han.)
#     # Anyway introduced phasing by beagle. (2018. 7. 16.)
#
#     '''
#     beagle unphased=$OUTPUT.bgl nsamples=4 niterations=10 missing=0 verbose=true maxwindow=1000 log=$OUTPUT.phasing >> $OUTPUT.bgl.log
#
#     '''
#
#     command = ' '.join([beagle, "unphased=" + OUTPUT + '.bgl',
#                         "nsamples=4 niterations=10 missing=0 verbose=true maxwindow=1000",
#                         "log=" + OUTPUT + '.phasing', ">>", OUTPUT + '.bgl.log'])
#     print(command)
#     os.system(command)
#
#
#     index += 1