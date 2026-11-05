# HLAgent v3

HLAgent is a natural-language agent for HLA imputation and fine-mapping. A single Streamlit app offers HLA expert question answering and an approval-gated HLA analysis pipeline. A deterministic engine performs every analysis; language models only route messages, propose plans and write narrative summaries.

| Mode | What it does |
|---|---|
| Mode 1: HLA expert | Answers questions from a local literature knowledge base (ChromaDB retrieval-augmented generation) and optional web search (Tavily). Citations are allowed only for passages that were actually retrieved. |
| Mode 2: analysis | Turns a request into an analysis plan and shows it on an approval card (steps, datasets, parameters, input warnings). Nothing runs until the user approves; the results are written to files and a report. |

Analysis steps (Node1–Node5 keep the meaning they had in HLAgent v1):

| Step | Purpose | Tools |
|---|---|---|
| Stage D | Input checks: genome-build detection, alignment to hg18 by rsID, MHC extraction (chr6:29–34 Mb), quality control | PLINK 1.9 |
| Stage I | HLA imputation, added automatically when HLA types are missing | CookHLA in Docker (pinned by digest, run offline) |
| Node1 | Binary HLA marker panel (alleles, amino-acid residues, intragenic SNPs, indels) | HATK IMGT2Seq, NomenCleaner, bMarkerGenerator |
| Node2 | Marker-level logistic or linear regression, with Manhattan, QQ and HLA heatmap plots | PLINK 1.9 (`--a1-allele`, HATK conventions) |
| Node3 | Stepwise conditional regression | PLINK 1.9 `--condition-list` |
| Stage P | Phasing of the Node1 panel, added automatically before Node4 | BEAGLE 3.3.2 with the BEAGLE utilities (HATK chain) |
| Node4 | Omnibus likelihood-ratio test for each amino-acid position | HATK `OmnibusTest_BHv5.R` |
| Node5 | Meta-analysis of two or more studies: inverse-variance fixed effect, Cochran's Q, I², DerSimonian–Laird random effects | Python (`hlagent.stats.meta`) |
| Stage R | Report (Markdown, single-file HTML and `facts.json`) | Jinja2 |

The statistical methods are described in [`docs/METHODS.md`](docs/METHODS.md).

## 1. Installation (WSL2 Ubuntu 22.04 or Linux)

### 1.1 Prerequisites

- **Memory:** CookHLA needs roughly `number of processes × Java memory + 2 GB`. On WSL2, set `memory=12GB` or more in `%UserProfile%\.wslconfig`.
- **Docker:** enable WSL integration in Docker Desktop, or install Docker Engine inside WSL.
- **mamba:** install [Miniforge](https://github.com/conda-forge/miniforge).
- **Working location:** on WSL2, the ext4 file system (`~/work/...`) is much faster than a Windows drive (`/mnt/f/...`).

```bash
git clone -b version3 https://github.com/dhkwnr97/HLAgent.git ~/work/HLAgent_v3
cd ~/work/HLAgent_v3
```

### 1.2 Tools and Python packages

Bioinformatics tools (PLINK, Java, R) are installed with mamba, and Python packages with uv.

```bash
mamba env create -f environment.yml
mamba activate hlagent3
uv pip install --python "$CONDA_PREFIX/bin/python" -e ".[dev]"
```

### 1.3 Reference resources and example data

The reference panel (1000G_REF), IPD-IMGT/HLA 3.32.0, the HATK dictionaries and the example data (about 1 GB) are not stored in this branch. Copy them from HLAgent v1:

```bash
# from a local copy of HLAgent v1
hlagent setup-resources --from-v1 /path/to/HLAgent-main_v1.0.0
# or clone v1 from GitHub
hlagent setup-resources --clone
# optional: UCSC chain files, so that CookHLA can lift hg19/hg38 input over itself
hlagent setup-resources --liftover-chains
```

### 1.4 CookHLA image

```bash
docker pull dhkwnr97/cookhla@sha256:0b374cef9cc352cfaa7aa5e89ad49d5b6c64274a6eb8100acbb7f6f452f0c5d6
```

### 1.5 API keys

```bash
cp .env.example .env
# Add GOOGLE_API_KEY (default model: Gemini). OpenAI, Anthropic, Tavily and TypeSafe (Jev) keys are optional.
```

Keys can also be entered on the Settings page of the web app. Keys entered there stay in the browser session's memory and are never written to files or logs. The analysis pipeline works without any key: a rule-based planner then builds the same approval card.

### 1.6 Check and start

```bash
hlagent doctor          # checks PLINK, Java, R, Docker, the CookHLA image, resources, memory and keys
hlagent ingest          # indexes the papers in knowledge/articles (needs a Google key)
hlagent ui              # http://localhost:8501
```

## 2. Usage

### 2.1 Chat page

Requests can be written in English or Korean.

| Example input | Result |
|---|---|
| `Explain the molecular mechanism linking HLA-DRB1*15:01 to multiple sclerosis` | Mode 1: knowledge-base search, then an answer with citations ([K1]) and references |
| `Run an HLA analysis on BMExample` | Mode 2: approval card (Node1 → Node4, with a warning about the synthetic spike-in phenotype). Edit the nodes on the card or click "Approve and run" |
| `Only up to Node2` (while a card is shown) | The plan is revised and a new card is shown |
| `Go ahead` / `Cancel` | Approve / decline the plan |
| `What is the status?` | Run status and the location of the report |
| `Meta-analyse BMExample and GenotypeExample` | For each study: Stage D → (Stage I for GenotypeExample) → Node1 → Node2, then Node5 |
| `Fine-map WTCCC_RA and meta-analyse it with the NBS_CD summary statistics` | Node1–Node4 on the real RA phenotype, then Node5 with the Crohn's disease summary statistics |

Results appear on the Results page: the HTML report, figures, tables, the list of files, a zip download and, optionally, an LLM-written summary that is inserted only if every number in it matches `facts.json`.

### 2.2 Command line (no GUI)

```bash
hlagent example-plan S2 --out s2.json    # BMExample, synthetic spike-in phenotype, Node1-4
hlagent run --plan s2.json
hlagent example-plan S5 --out s5.json    # WTCCC RA (Node1-4) + NBS Crohn's disease summary statistics (Node5)
hlagent run --plan s5.json
```

| Scenario | Data | Notes |
|---|---|---|
| S2 | BMExample (HapMap CEU families, four-field HLA types) | No phenotype (−9), so a synthetic spike-in phenotype (DRB1\*15:01, OR 5) is used; demonstration only |
| S3 | GenotypeExample (1958 Birth Cohort, hg19, n = 10) | No HLA types, so CookHLA imputes them; the phenotype is constant, so a synthetic null phenotype is used; demonstration only |
| S4 | S2 + S3 | Meta-analysis of the two studies (pipeline demonstration) |
| S5 | WTCCC 58C vs RA (300 + 300) + NBS vs Crohn's disease summary statistics | Real phenotypes; example of a two-phenotype meta-analysis |

### 2.3 Your own data (Data page)

Files uploaded to `workspace/<name>/` are recognised as a dataset:

| File | Format |
|---|---|
| `*.bed/.bim/.fam` | PLINK 1 binary SNP genotypes (one set) |
| `*.chped` or `*.hped` | HLA types (six PLINK columns plus two alleles per gene). Without them, CookHLA imputes the HLA types |
| `*.phe` / `*.pheno` | Table with a header `FID IID <phenotype name> ...`; binary traits use 1 = control, 2 = case |
| `*.assoc.logistic` + `.bim` | External summary statistics (Node5 only) |

If the folder name contains the build (for example `hg19`), that build is used; otherwise Stage D detects it. Language models receive only file names and summary information (sample counts, build, case and control counts), never individual-level genotypes or phenotypes.

## 3. Output layout

```text
runs/<date>_<goal>_<plan_id>/
  plan.json  params.lock.json  env.lock.json  reproduce.sh  status.json
  <study>/staged/      quality-controlled hg18 SNPs, HLA types, pheno.tsv, preflight.json
  <study>/stagei/      CookHLA output, imputation_qc.json
  <study>/node1/       panel.{bed,bim,fam}
  <study>/node2/       assoc.assoc.logistic, top_markers.tsv, manhattan.png, qq.png, heatmap.*.png
  <study>/node3/       conditional_steps.tsv, round*.assoc.logistic
  <study>/stagep/      panel.bgl.phased, panel.aa
  <study>/node4/       *.omnibus, omnibus.*.png
  node5/               meta.tsv, top_meta.tsv, harmonization.json, forest.*.png, meta_manhattan.png
  report/              report.md, report.html, facts.json, figures.json
  logs/                events.jsonl, runner.jsonl, commands.jsonl
```

Each step folder contains a `node_result.json` with the commands, parameters, tool versions, metrics and warnings of that step. Re-running in the same run folder reuses every step whose inputs and parameters are unchanged.

## 4. Tests

```bash
pytest -q -m "not golden and not slow"   # unit, agent (FunctionModel) and UI (AppTest) tests: a few seconds
pytest -q -m "golden and not slow"       # reproduction of published HATK results (G1, G3, G4, G5): about 3 minutes
pytest -q -m slow                         # CookHLA in Docker (G2) and the BEAGLE phasing invariant: about 15 minutes
```

| Test | Criterion |
|---|---|
| G1 | Reproduces the HATK RA example `assoc.logistic` (OR, SE and P agree at PLINK's printed precision) |
| G2 | CookHLA on the 1958 Birth Cohort example: allele calls identical to the HLAgent v1 run |
| G3 | Omnibus test: same variants, degrees of freedom, N and residues; Spearman correlation of −log10 P ≥ 0.95; same top hit (AA_DRB1_96) |
| G4 | Meta-analysis identical to the HATK implementation and to the hand-checked values in `docs/METHODS.md` |
| G5 | Node1 panel: no HLA, amino-acid or insertion genotype differs from the published panel |

## 5. Benchmarks

- `benchmarks/workflow/`: end-to-end runs of four tasks (B1–B4), agreement with the published HATK and stand-alone CookHLA results, run time per step and the manual effort of the equivalent command-line route. `python benchmarks/workflow/run_benchmark.py --out benchmarks/workflow/results --reps 3` runs the tasks; `concordance.py`, `conventional.py` and `summarize.py` produce the tables and the figure.
- `benchmarks/planning/`: 47 planning tasks and 14 routing items that measure how accurately a language model plans each analysis step. Run `hlagent eval-planning --models google:<model>,openai:<model>,anthropic:<model> --repeats 5 --out benchmarks/planning/results`; `--models oracle,naive` checks the harness without API keys.

## 6. Known limitations

- BMExample and GenotypeExample have no usable phenotype, so they run only with synthetic phenotypes. Every artifact and report marks them `SYNTHETIC`; they carry no biological meaning. S5 (RA and Crohn's disease) is the example with real phenotypes.
- In BMExample, the spike-in (OR 5) is estimated as OR 1.975 (95% CI 0.846–4.61) in the 74 people with DRB1 types. This reflects the small sample, not an error in the generator, and the report shows it as is.
- CookHLA's own liftover of hg19/hg38 input is used only when the chain files are installed, and this path has not been tested in a network-restricted environment. The default path (rsID re-mapping to hg18) is tested.
- Jev (TypeSafe) is in early access. Without its key, the language model routes messages; without any model key, keyword rules do.
- Sequencing-based HLA typing (OptiType, HLA-HD) and the A2A/MCP interfaces of HLAgent v1 are not part of version 3.

Changes made to the vendored HATK code are listed in [`docs/CHANGES_vendor.md`](docs/CHANGES_vendor.md); coding rules for contributors and coding agents are in [`CLAUDE.md`](CLAUDE.md).

## 7. License and citation

HLAgent code is released under the MIT license. The vendored HATK code and CookHLA may be used for non-commercial academic research only.
When you publish results, please cite HATK (Choi et al., *Bioinformatics* 2021), CookHLA (Cook et al., *Nat Commun* 2021), BEAGLE 3 (Browning and Browning, *Am J Hum Genet* 2007), PLINK 1.9 (Chang et al., *GigaScience* 2015) and the omnibus test (Raychaudhuri et al., *Nat Genet* 2012).
