# Changes to vendored code (`vendor/hatk_port/`)

Source: HLAgent v1 `src/tools/HATK` (a port of HATK, Choi et al., *Bioinformatics* 2021;37:416–418). HATK is licensed for non-commercial academic use only. The statistical logic is unchanged; every change below is limited to packaging, paths or input layout, and the golden tests were re-run after each one.

| # | File | Change | Why | Effect on statistics | Verified by |
|---|---|---|---|---|---|
| 1 | all modules | Imports rewritten from `src.tools.HATK.` to `hatk_port.`; new package `__init__.py` | Install as a package without the v1 tree | None | G1, G3, G5 |
| 2 | Not copied | `Runners/`, YAML configs, bundled IMGT/HLA data, dependency installers | v3 has its own runner and settings; IMGT data lives in `resources/imgt/` | None | n/a |
| 3 | `bMarkerGenerator/src/encodeHLA.py` | `_p_data` default resolved relative to the package (`IMGT2Seq/data_for_imgt2seq`) instead of the current working directory | v1 depended on the process cwd | None | G5 |
| 4 | `IMGT2Seq/IMGT2Seq.py` | IMGT/HLA directory taken from `HLAGENT_IMGT_DIR` when set | Use `resources/imgt/` without downloading | None (same IMGT 3.32.0 files) | G5 dictionaries |
| 5 | `bMarkerGenerator/bMarkerGenerator.py` | New `_subset_dictionary_map()`: the AA and SNPS map files are filtered to the genes present in the CHPED instead of copying the full 8-gene dictionary map (`cp`) | With fewer than 8 genes (BMExample has no DPA1/DPB1; CookHLA's 1000G panel imputes 5 genes) the sequence PED and the copied MAP had different column counts and `encodeVariants` crashed. HLAgent also drops all-missing genes and orders gene columns as in the dictionary (`node1_bmarker.truncate_chped`) | None: identical output when all 8 genes are present | G5 (WTCCC RA panel, 8 genes: 0 genotype mismatches vs the published panel); S2 and S3 scenarios |

Rule (CLAUDE.md §8): any further change must keep G1–G5 passing and be added to this table.
