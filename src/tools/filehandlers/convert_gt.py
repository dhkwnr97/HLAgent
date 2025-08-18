"""
This script automatically detects the genotype input file format (VCF, BCF, PGEN, PED/MAP, TPED/TFAM, BGEN, GEN) and converts it to PLINK binary format (.bed/.bim/.fam).

- Reads input and output file paths from a YAML config file (convert_gt_run_config.yaml)
- Detects the input format based on file extensions
- Runs the appropriate PLINK2/PLINK1/bcftools command to generate .bed/.bim/.fam files

Usage:
    python convert_gt.py [config_path]

Config YAML example:
    _input_files: [data/input/my.tped, data/input/my.tfam]
    _output_dir: data/output/ConvertGT
"""

import os
import subprocess
import yaml
from pathlib import Path
import tempfile

def detect_input_format(input_files):
    # Detect input format based on file extensions
    exts = [Path(f).suffix if not f.endswith('.vcf.gz') else '.vcf.gz' for f in input_files]
    files = {ext: f for ext, f in zip(exts, input_files)}

    if '.bcf' in exts:
        return 'bcf', files['.bcf']
    if '.vcf' in exts or '.vcf.gz' in exts:
        return 'vcf', files.get('.vcf', files.get('.vcf.gz'))
    elif all(e in exts for e in ['.pgen', '.pvar', '.psam']):
        prefix = Path(files['.pgen']).with_suffix('').as_posix()
        return 'pgen', prefix
    elif all(e in exts for e in ['.ped', '.map']):
        return 'ped', (files['.ped'], files['.map'])
    elif all(e in exts for e in ['.tped', '.tfam']):
        prefix = Path(files['.tped']).with_suffix('').as_posix()
        return 'tped', prefix
    elif all(e in exts for e in ['.bgen', '.sample']):
        return 'bgen', (files['.bgen'], files['.sample'])
    elif all(e in exts for e in ['.gen', '.sample']):
        return 'gen', (files['.gen'], files['.sample'])
    else:
        raise ValueError("Unsupported input format")

def convert_to_plink(fmt, files, output_dir):
    os.makedirs(Path(output_dir).parent, exist_ok=True)
    if fmt == 'bcf':
        # Convert BCF to VCF.gz using bcftools, then to PLINK
        with tempfile.NamedTemporaryFile(suffix='.vcf.gz', delete=False) as tmpvcf:
            tmpvcf_path = tmpvcf.name
        subprocess.run(['bcftools', 'view', '-Oz', '-o', tmpvcf_path, files], check=True)
        subprocess.run(['plink2', '--vcf', tmpvcf_path, '--make-bed', '--out', output_dir], check=True)
        os.remove(tmpvcf_path)
    elif fmt == 'vcf':
        subprocess.run(['plink2', '--vcf', files, '--make-bed', '--out', output_dir], check=True)
    elif fmt == 'pgen':
        subprocess.run(['plink2', '--pfile', files, '--make-bed', '--out', output_dir], check=True)
    elif fmt == 'ped':
        ped, mapf = files
        subprocess.run(['plink', '--ped', ped, '--map', mapf, '--make-bed', '--out', output_dir], check=True)
    elif fmt == 'tped':
        subprocess.run(['plink', '--tfile', files, '--make-bed', '--out', output_dir], check=True)
    elif fmt == 'bgen':
        bgen, sample = files
        subprocess.run(['plink2', '--bgen', bgen, '--sample', sample, '--make-bed', '--out', output_dir], check=True)
    elif fmt == 'gen':
        gen, sample = files
        subprocess.run(['plink2', '--gen', gen, '--sample', sample, '--make-bed', '--out', output_dir], check=True)
    print(f"[Done] {output_dir}.bed/.bim/.fam created.")

def main(config_path='convert_gt_run_config.yaml'):
    with open(config_path) as f:
        cfg = yaml.safe_load(f)
    input_files = cfg['_input_files']
    output_dir = cfg['_output_dir']
    fmt, files = detect_input_format(input_files)
    convert_to_plink(fmt, files, output_dir)

if __name__ == '__main__':
    main()