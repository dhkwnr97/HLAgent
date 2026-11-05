"""Manual effort of the conventional route vs HLAgent for benchmark scenarios B1-B4.

The conventional protocols are the shortest command sequences we could assemble from the tools' own
documentation (HATK v2 README whole-pipeline command; HATK v1 module docs for meta-analysis, conditional
omnibus, NomenCleaner, bMarkerGenerator, logistic regression and plots; CookHLA README; PLINK 1.9; UCSC
liftOver). PLINK, BEAGLE and R invocations match those recorded in HLAgent's command ledger. Paths are
written relative to one working directory, which favours the conventional route (shortest typing).

Human time is a keystroke-level model (KLM; Card, Moran & Newell 1980, Commun ACM 23:396-410) estimate
of error-free expert execution: it excludes reading documentation, inspecting outputs and debugging, so
it is a lower bound for the conventional route.

    python benchmarks/workflow/conventional.py --out benchmarks/workflow/results
"""

from __future__ import annotations

import argparse
import json
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

# KLM operator times (seconds), Card, Moran & Newell (1980) Table 2
K_SKILLED, K_AVERAGE = (
    0.20,
    0.28,
)  # keystroke: average skilled typist (55 wpm); average non-secretary (40 wpm)
M = 1.35  # mental preparation
P = 1.10  # point with mouse
H = 0.40  # home hands between keyboard and mouse
B = 0.10  # mouse button press or release

COOKHLA = "dhkwnr97/cookhla@sha256:0b374cef9cc352cfaa7aa5e89ad49d5b6c64274a6eb8100acbb7f6f452f0c5d6"
AGM = "AGM.1958BC.hg19.COPY.LiftDown_hg18.NoAmbig+1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC"
RA = "wtccc_filtered_58C_RA.hatk.300+300"
CD = "RESULT_EXAMPLE_wtccc_filtered_NBS_CD.hatk.300+300.chr6.hg18"


@dataclass
class Cmd:
    step: str
    line: str
    outputs: list[str] = field(default_factory=list)
    source: str = ""


@dataclass
class Protocol:
    scenario: str
    hlagent_request: str
    hlagent_clicks: int  # approval of the plan card plus any clarification choices
    commands: list[Cmd]
    decisions: list[str]  # manual judgements the conventional route leaves to the user
    not_covered: list[str]  # HLAgent outputs with no conventional command (not counted above)


def _wtccc_qc() -> Cmd:
    return Cmd(
        "Stage D",
        f"plink --bfile {RA}.hg18.chr6.29-34mb --chr 6 --from-mb 29 --to-mb 34 --geno 0.05 "
        "--mind 0.05 --maf 0.01 --hwe 1e-6 --make-bed --allow-no-sex --keep-allele-order --out RA.qc",
        ["RA.qc"],
        "PLINK 1.9",
    )


def _hatk_whole(chped: str, bfile: str, pheno: str, pheno_name: str, out: str) -> Cmd:
    return Cmd(
        "Node1-2, Stage P, Node4",
        f"python HATK.py --hg 18 --chped {chped} --bfile {bfile} --pheno {pheno} "
        f"--pheno-name {pheno_name} --imgt 3320 --imgt-dir IMGTHLA3320 --multiprocess 4 --out {out} "
        "--java-mem 4g --nthreads 4",
        [out],
        "HATK v2 README, whole pipeline",
    )


def _stepwise(prefix: str, pheno: str, pheno_name: str, rounds: list[str]) -> list[Cmd]:
    """Stepwise conditional regression by hand: count tests (Bonferroni), inspect top hit, add it, refit."""
    cmds = [
        Cmd(
            "Node3",
            f"awk 'NR>1 && $12!=\"NA\"' {prefix}.assoc.logistic | wc -l",
            [],
            "Bonferroni denominator",
        ),
        Cmd("Node3", f"sort -g -k 12 {prefix}.assoc.logistic | head -n 3", [], "round 1 top marker"),
    ]
    for k in range(1, len(rounds) + 1):  # round k+1 conditions on the markers selected in rounds 1..k
        r = k + 1
        cmds += [
            Cmd(
                "Node3", f"printf '%s\\n' {' '.join(rounds[:k])} > cond.round{r}.txt", [f"cond.round{r}.txt"]
            ),
            Cmd(
                "Node3",
                f"plink --bfile {prefix} --pheno {pheno} --pheno-name {pheno_name} --logistic "
                f"hide-covar --ci 0.95 --condition-list cond.round{r}.txt --allow-no-sex --keep-allele-order "
                f"--out round{r}",
                [f"round{r}"],
                "PLINK 1.9",
            ),
            Cmd("Node3", f"sort -g -k 12 round{r}.assoc.logistic | head -n 3", [], f"round {r} top marker"),
        ]
    return cmds


def _heatmaps(assoc: str, genes: list[str], out: str) -> list[Cmd]:
    return [
        Cmd(
            "Node2 plots",
            f"python HATK.py --heatmap --ar {assoc} --HLA {g} "
            f"--maptable HLA_MAPTABLE_{g}.hg18.imgt3320.txt --out {out}",
            [f"{out}.{g}"],
            "HATK v1 docs 5-2",
        )
        for g in genes
    ]


def protocols() -> list[Protocol]:
    b1 = Protocol(
        "B1_WTCCC_RA_Node1-5",
        "Run the complete HLA fine-mapping pipeline on WTCCC_RA and then meta-analyze it with NBS_CD.",
        1,
        [
            _wtccc_qc(),
            _hatk_whole(f"{RA}.imgt3320.2field.chped", "RA.qc", f"{RA}.phe", "RA", "hatk/RA"),
            *_stepwise("hatk/RA", f"{RA}.phe", "RA", ["SNPS_DQA1_348_32713561_intron1"]),
            Cmd(
                "Node5",
                f"python HATK.py --metaanalysis --s1-logistic-result hatk/RA.assoc.logistic --s1-bim hatk/RA.bim "
                f"--s2-logistic-result {CD}.assoc.logistic --s2-bim {CD}.bim --out meta/RA_CD",
                ["meta/RA_CD"],
                "HATK v1 docs 4-3 (not exposed by the v2 command line)",
            ),
        ],
        [
            "confirm the genome build of the genotypes (HATK leaves build consistency to the user)",
            "round 1: compare the top P with the Bonferroni threshold and choose the conditioning marker",
            "round 2: decide to stop",
        ],
        [
            "forest plots of the top meta-analysis markers",
            "meta-analysis Manhattan plot",
            "report with numbers checked against the result tables",
            "provenance bundle (reproduce.sh, locks, hashes)",
        ],
    )
    b2 = Protocol(
        "B2_WTCCC_RA_Node4_cond_DRB1_96",
        "Run the omnibus test in WTCCC_RA conditioned on HLA-DRB1 amino-acid position 96 (AA_DRB1_96).",
        1,
        [
            _wtccc_qc(),
            _hatk_whole(f"{RA}.imgt3320.2field.chped", "RA.qc", f"{RA}.phe", "RA", "hatk/RA"),
            Cmd(
                "Node4",
                f"python3 HATK.py --omnibus --fam hatk/RA.fam --phased hatk/RA.bgl.phased --out omnibus/RA "
                f"--pheno {RA}.phe --pheno-name RA --condition AA_DRB1_96",
                ["omnibus/RA"],
                "HATK v1 docs 4-1",
            ),
        ],
        ["confirm the genome build of the genotypes"],
        ["omnibus Manhattan plot of the conditional test", "report and provenance bundle"],
    )
    b3 = Protocol(
        "B3_GenotypeExample_CookHLA_Node1-2",
        "GenotypeExample only has SNP array genotypes. Impute the classical HLA alleles with CookHLA, build the "
        "HLA binary marker panel and test the markers for association.",
        2,  # plan approval + choice of a synthetic null phenotype (the input phenotype is constant)
        [
            Cmd(
                "Stage D",
                "plink --bfile 1958BC.hg19 --chr 6 --geno 0.05 --mind 0.05 --make-bed --allow-no-sex "
                "--keep-allele-order --out 1958BC.hg19.qc",
                ["1958BC.hg19.qc"],
                "PLINK 1.9",
            ),
            Cmd(
                "Stage I",
                f"docker run --rm --user $(id -u):$(id -g) -v $PWD:/data -w /data {COOKHLA} CookHLA.py "
                "-i 1958BC.hg19.qc -hg 19 -o out/1958BC+1000G_REF.EUR -ref ref/1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC "
                f"-gm {AGM}.mach_step.avg.clpsB -ae {AGM}.aver.erate -mem 4g",
                ["out/1958BC+1000G_REF.EUR"],
                "CookHLA README (Docker); CookHLA lifts hg19 input down to the hg18 panel itself",
            ),
            Cmd(
                "Stage I",
                "awk '$8 < 0.8' out/1958BC+1000G_REF.EUR.MHC.HLA_IMPUTATION_OUT.alleles | cut -d ' ' -f 3 "
                "| sort | uniq -c",
                [],
                "low-confidence calls per gene",
            ),
            Cmd(
                "Node1",
                "python3 HATK.py --nomencleaner --hat HLA_ALLELE_TABLE.imgt3320.hat "
                "--hped out/1958BC+1000G_REF.EUR.MHC.HLA_IMPUTATION_OUT.hped --out 1958BC.2field --2field --imgt 3320",
                ["1958BC.2field"],
                "HATK v1 docs 3",
            ),
            Cmd(
                "Node1",
                "python3 HATK.py --bmarkergenerator --variants out/1958BC.hg19.qc.COPY.LiftDown_hg18.NoAmbig "
                "--chped 1958BC.2field.chped "
                "--out panel/1958BC --hg 18 --dict-AA HLA_DICTIONARY_AA.hg18.imgt3320 "
                "--dict-SNPS HLA_DICTIONARY_SNPS.hg18.imgt3320",
                ["panel/1958BC"],
                "HATK v1 docs 2",
            ),
            Cmd(
                "Node2",
                "awk 'BEGIN{print \"FID IID SYNTHETIC\"; srand(20261023)} {print $1, $2, (rand()<0.5)?2:1}' "
                "1958BC.hg19.qc.fam > null.phe",
                ["null.phe"],
                "synthetic null phenotype",
            ),
            Cmd(
                "Node2",
                "python HATK.py --logistic --input panel/1958BC --pheno-name SYNTHETIC --pheno null.phe "
                "--out assoc/1958BC",
                ["assoc/1958BC"],
                "HATK v1 docs 4-2",
            ),
            Cmd(
                "Node2 plots",
                "python HATK.py --manhattan --ar assoc/1958BC.assoc.logistic --imgt 3320 --hg 18 "
                "--out plots/1958BC",
                ["plots/1958BC"],
                "HATK v1 docs 5-1",
            ),
            *_heatmaps("assoc/1958BC.assoc.logistic", ["A", "C", "DQB1", "DRB1"], "plots/1958BC"),
        ],
        [
            "identify the genome build (hg19) for CookHLA and pick the hg18 copy of the genotypes for HATK",
            "choose the reference panel and check that an adaptive genetic map matches it",
            "decide how to treat genes the panel cannot impute (DPA1, DPB1, DQA1)",
            "decide what to do about the constant phenotype",
        ],
        ["imputation QC summary (per-gene confidence, DR2)", "report and provenance bundle"],
    )
    b4 = Protocol(
        "B4_BMExample_Node1-4",
        "Use BMExample: build the HLA marker panel, test association, run stepwise conditional analysis and the "
        "omnibus test.",
        2,  # plan approval + choice of a synthetic spike-in phenotype (no phenotype in the input)
        [
            Cmd(
                "Stage D",
                "awk 'NR==FNR{pos[$2]=$4; next} ($2 in pos){print $2\"\\t\"pos[$2]}' "
                "1000G_REF.EUR.chr6.hg18.29mb-34mb.inT1DGC.bim HAPMAP_CEU.bim > remap.txt",
                ["remap.txt"],
                "rsID-based re-mapping to hg18",
            ),
            Cmd(
                "Stage D",
                "plink --bfile HAPMAP_CEU --extract remap.txt --update-map remap.txt --make-bed "
                "--allow-no-sex --keep-allele-order --out CEU.hg18",
                ["CEU.hg18"],
                "PLINK 1.9",
            ),
            Cmd(
                "Stage D",
                "plink --bfile CEU.hg18 --chr 6 --from-mb 29 --to-mb 34 --filter-founders --geno 0.05 "
                "--mind 0.05 --maf 0.01 --hwe 1e-6 --make-bed --allow-no-sex --keep-allele-order --out CEU.qc",
                ["CEU.qc"],
                "PLINK 1.9",
            ),
            Cmd(
                "Node1",
                "cut -f 1-12,17-22 HAPMAP_CEU_HLA.imgt3320.4field.chped > CEU.noDP.chped",
                ["CEU.noDP.chped"],
                "drop untyped DPA1/DPB1 columns (all '0'), which break HATK's positional gene layout",
            ),
            Cmd(
                "Node1",
                "python3 HATK.py --nomencleaner --hat HLA_ALLELE_TABLE.imgt3320.hat --hped CEU.noDP.chped "
                "--out CEU.2field --2field --imgt 3320",
                ["CEU.2field"],
                "HATK v1 docs 3",
            ),
            Cmd(
                "Node2",
                "python spike_in_phenotype.py --chped CEU.2field.chped --fam CEU.qc.fam --allele DRB1*15:01 "
                "--odds-ratio 5 --seed 20261023 --out spike.phe",
                ["spike.phe"],
                "user-written script: no standard tool simulates a spike-in phenotype",
            ),
            _hatk_whole("CEU.2field.chped", "CEU.qc", "spike.phe", "SYNTHETIC", "hatk/CEU"),
            *_stepwise("hatk/CEU", "spike.phe", "SYNTHETIC", []),
        ],
        [
            "recognise that the positions match no standard build and choose a re-mapping strategy",
            "restrict association to founders (family data)",
            "identify untyped genes in the 4-field typing and remove them",
            "decide how to obtain a phenotype for a demonstration run",
            "round 1: compare the top P with the Bonferroni threshold and stop",
        ],
        ["report and provenance bundle"],
    )
    return [b1, b2, b3, b4]


def units(line: str) -> tuple[int, list[str]]:
    """Cognitive units of a command line: each program, each flag with its values, each positional argument."""
    toks = shlex.split(re.sub(r"\$\([^)]*\)", "X", line), posix=True)  # $(id -u) is one value, not flags
    n, tools, expect_prog, in_flag = 0, [], True, False
    for t in toks:
        if t in ("|", ">", ">>", "<"):
            n += 1
            expect_prog, in_flag = t == "|", False
            continue
        if expect_prog:
            tools.append(
                t if t not in ("python", "python3") else "python HATK.py" if "HATK.py" in line else t
            )
            n += 1
            expect_prog, in_flag = False, False
            continue
        if t.startswith("-") and not t.lstrip("-").replace(".", "").isdigit():
            n += 1
            in_flag = True
        elif not in_flag:
            n += 1
    return n, tools


def score(p: Protocol) -> dict:
    rows = []
    for i, c in enumerate(p.commands):
        n_units, tools = units(c.line)
        later = " ".join(x.line for x in p.commands[i + 1 :])
        rows.append(
            {
                "step": c.step,
                "n_chars": len(c.line),
                "n_units": n_units,
                "tools": tools,
                "n_outputs_named": len(c.outputs),
                "n_handoffs": sum(o in later for o in c.outputs),
                "source": c.source,
                "line": c.line,
            }
        )
    chars = sum(r["n_chars"] for r in rows)
    n_units = sum(r["n_units"] for r in rows)
    out: dict = {
        "scenario": p.scenario,
        "conventional": {
            "n_commands": len(rows),
            "n_units": n_units,
            "n_chars": chars,
            "n_tools": len({t for r in rows for t in r["tools"]}),
            "tools": sorted({t for r in rows for t in r["tools"]}),
            "n_files_named": sum(r["n_outputs_named"] for r in rows),
            "n_handoffs": sum(r["n_handoffs"] for r in rows),
            "n_decisions": len(p.decisions),
            "decisions": p.decisions,
            "not_covered": p.not_covered,
            "commands": rows,
        },
        "hlagent": {
            "request": p.hlagent_request,
            "n_chars": len(p.hlagent_request),
            "n_clicks": p.hlagent_clicks,
            "n_commands": 0,
        },
    }
    for tag, k in (("skilled", K_SKILLED), ("average", K_AVERAGE)):
        conv = (
            M * n_units + k * (chars + len(rows)) + M * len(p.decisions)
        )  # +1 keystroke (Enter) per command
        hla = M + k * (len(p.hlagent_request) + 1) + p.hlagent_clicks * (M + H + P + 2 * B)
        out["conventional"][f"klm_seconds_{tag}"] = round(conv, 1)
        out["hlagent"][f"klm_seconds_{tag}"] = round(hla, 1)
    return out


def write_scripts(ps: list[Protocol], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    for p in ps:
        lines = [
            "#!/usr/bin/env bash",
            f"# Conventional route for {p.scenario} (see benchmarks/workflow/conventional.py).",
            "# Paths are relative to one working directory holding the inputs, dictionaries and reference panel.",
            f'# HLAgent equivalent: "{p.hlagent_request}" + {p.hlagent_clicks} click(s).',
            "set -euo pipefail",
        ]
        step = None
        for c in p.commands:
            if c.step != step:
                lines += ["", f"# --- {c.step}"]
                step = c.step
            lines += ([f"# {c.source}"] if c.source else []) + [c.line]
        lines += ["", "# Manual decisions:"] + [f"#  - {d}" for d in p.decisions]
        (out_dir / f"{p.scenario}.sh").write_text("\n".join(lines) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    ps = protocols()
    res = [score(p) for p in ps]
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "effort.json").write_text(json.dumps(res, indent=1))
    write_scripts(ps, a.out.parent / "conventional")
    for r in res:
        c, h = r["conventional"], r["hlagent"]
        print(
            f"{r['scenario']}: conventional {c['n_commands']} cmds, {c['n_units']} units, {c['n_chars']} chars, "
            f"{c['n_tools']} tools, {c['n_files_named']} files ({c['n_handoffs']} hand-offs), "
            f"{c['n_decisions']} decisions, KLM {c['klm_seconds_skilled']}-{c['klm_seconds_average']} s | "
            f"HLAgent {h['n_chars']} chars + {h['n_clicks']} clicks, KLM {h['klm_seconds_skilled']}-"
            f"{h['klm_seconds_average']} s"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
