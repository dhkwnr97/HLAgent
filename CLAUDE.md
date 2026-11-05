# HLAgent v3: rules for coding agents

HLAgent v3 is a Streamlit app with two modes: HLA expert Q&A (RAG and web search) and an approval-gated HLA analysis pipeline: Stage D (data QC) → Stage I (HLA imputation, CookHLA Docker) → Node1–5 (v1 HATK analysis nodes: Node1 binary marker panel, Node2 regression, Node3 stepwise conditional, Node4 omnibus, Node5 meta-analysis) with Stage P (BEAGLE phasing) between Node1 and Node4 → Stage R (report). Keep the v1 meaning of "Node1–5"; imputation and phasing are stages, not nodes. A2A is out of scope. The design and the statistical methods are summarised in `README.md` and `docs/METHODS.md`.

## Non-negotiable rules

1. **Look up docs before coding.** Query Context7 for every library before writing code that uses it. Do not rely on memory for APIs.
   - Pydantic AI: `/pydantic/pydantic-ai` (v2 line; the installed version is pinned in `pyproject.toml`)
   - Streamlit: `/streamlit/streamlit`
   - Chroma: `/chroma-core/chroma`
   - Resolve any other library (Tavily, typesafe-sdk, sentence-transformers, pymupdf) with `resolve-library-id` first.
2. **Keep LLMs out of the computation path.** LLMs plan, route, and narrate. Every computation is a deterministic node function that returns `NodeResult`. Never execute LLM-generated code or shell strings.
3. **Run external tools only through `hlagent.tools.proc.run(cmd: list[str], ...)`.** Never use `shell=True` or `os.system`. Record every command in `NodeResult.commands`.
4. **Use strict parameter models.** Every model uses `extra="forbid"` and `Field` bounds. Do not add config keys the code does not read (v1 defect D6).
5. **Protect data.** Never send individual-level genotype or phenotype data to an LLM, Jev, or Tavily. Send aggregated statistics only, via `facts.json`.
6. **Protect secrets.** API keys are `SecretStr`. Never log, persist, or echo them. GUI keys stay in session memory unless the user opts in to saving them. `.env` is gitignored.
7. **Write only under the run directory.** Nodes read inputs through `ArtifactRef` and write only inside `runs/<run_id>/...`. Never infer outputs by scanning folders (v1 defect D5).
8. **Treat vendor statistics as frozen.** Do not change the statistical logic in `vendor/hatk_port/` unless golden tests G1–G4 still pass. Log every vendor change in `docs/CHANGES_vendor.md`.
9. **Pin the CookHLA image by digest.** The image entrypoint is micromamba's `_entrypoint.sh`, workdir `/opt/CookHLA`, default user `mambauser`; call `CookHLA.py ...` or `python -m MakeGeneticMap ...` after the image name. Use `dhkwnr97/cookhla@sha256:0b374cef9cc352cfaa7aa5e89ad49d5b6c64274a6eb8100acbb7f6f452f0c5d6`. Run with `--user UID:GID`, enforce the memory budget, and omit `-mp` when it is 1.
10. **Never mislabel synthetic data.** A run that uses a synthetic phenotype is marked `SYNTHETIC` in every artifact and report, and the mark cannot be disabled.
11. **Phasing follows the HATK chain.** Stage P runs PLINK → `linkage2beagle.jar` → GC trick → `redefineBP` → BEAGLE 3.3.2 (`seed=` always passed) → unGCtrick → `AllCC_Get_Phased_AA_Calls.R`. Do not replace it with a generic VCF phaser.

## Environment (WSL2 Ubuntu 22.04)

```bash
mamba env create -f environment.yml && mamba activate hlagent3
uv pip install --python "$CONDA_PREFIX/bin/python" -e ".[dev]"
hlagent doctor
```

- Bioinformatics and system tools (plink, plink2, openjdk, R, bcftools, ucsc-liftover) come from mamba only.
- Python packages come from uv only. Never use bare `pip`.
- Work on ext4 (`~/work/...`), not `/mnt/f/...`, for runs and resources.

## Commands

| Purpose | Command |
|---|---|
| Lint and format | `ruff check . && ruff format --check . && pyright` |
| Fast tests | `pytest -q -m "not golden and not slow"` |
| Golden tests (G1–G4) | `pytest -q -m golden` |
| End-to-end CLI (Docker) | `pytest -q -m slow` |
| Headless run | `hlagent run --plan runs/<id>/plan.json` |
| UI | `streamlit run src/hlagent/ui/app.py` |

## Testing rules

- Unit tests never call real model APIs. Set `pydantic_ai.models.ALLOW_MODEL_REQUESTS = False` in `conftest.py` and use `TestModel` / `FunctionModel`.
- Every statistical function needs a test with hand-checked values. For meta-analysis use the reference values in `docs/METHODS.md`.
- A change is done only when its tests pass. Report failures with their output and never mark work done while tests fail.

## Conventions

- Python 3.12, full type hints, Pydantic v2, `pathlib.Path`, standard `logging` with a JSON formatter and secret-redaction filter.
- Code, comments, and identifiers are in English. User-facing text follows the user's language (Korean or English).
- Use HLA nomenclature exactly (for example `HLA-DRB1*15:01`). In reports, keep genome builds explicit (hg18, hg19, hg38).
