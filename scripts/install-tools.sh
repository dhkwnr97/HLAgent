#!/usr/bin/env bash
set -euo pipefail
if [[ ${EUID} -ne 0 ]]; then
    sudo apt-get update
    sudo apt-get install -y --no-install-recommends default-jre-headless plink2 plink1.9 bcftools r-base-core r-cran-metafor
else
    apt-get update
    apt-get install -y --no-install-recommends default-jre-headless plink2 plink1.9 bcftools r-base-core r-cran-metafor
fi
task_tools="${HLAGENT_HOME:-${HOME}/.local/share/hlagent}/tools"
mkdir -p -- "${task_tools}"
mkdir -p -- "${task_tools}/chains"
for task_build in hg19 hg38; do
    curl -fLsS "https://hgdownload.soe.ucsc.edu/goldenPath/${task_build}/liftOver/${task_build}ToHg18.over.chain.gz" -o "${task_tools}/chains/${task_build}ToHg18.over.chain.gz"
done
curl -fLsS https://faculty.washington.edu/browning/beagle/beagle.27Feb25.75f.jar -o "${task_tools}/beagle.27Feb25.75f.jar"
printf '%s  %s\n' '7319f4af9638be05c18dcc1bfb8fb41a58a09293507ebf0d54617d0e40df5a70' "${task_tools}/beagle.27Feb25.75f.jar" | sha256sum --check
printf '%s  %s\n' 'fc312e924e970dee936a69972768c6f84591d3a6daddbe598e49321c5fb1d253' "${task_tools}/chains/hg19ToHg18.over.chain.gz" | sha256sum --check
printf '%s  %s\n' '4ab6888f3903e815735f72777679efb0b1de3e9611b32f190af3ab73a7c96eff' "${task_tools}/chains/hg38ToHg18.over.chain.gz" | sha256sum --check
docker pull dhkwnr97/cookhla@sha256:0b374cef9cc352cfaa7aa5e89ad49d5b6c64274a6eb8100acbb7f6f452f0c5d6
