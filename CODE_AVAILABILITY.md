# Supplementary Software Availability

- **Software Title**: Gemini-Assisted Scoring of Building Deconstruction Research Evidence
- **Version**: `0.3.0`
- **Package Date**: 8 November 2026
- **Active Repaired Sealed Hash**: `a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d`
- **Licence**: MIT Licence

This software archive provides the repaired and verified scoring workflow, verbatim scoring rubric, exact 25 research-gap subgroup definitions, prompt construction and split-selection logic, pre-call attempt and USD budget guards, provenance reconstruction, review-packet generation, programmatic benchmark audit scripts, dependency pins, and offline regression suite for the systematic literature review on *Digital Support for Building Deconstruction Sequencing and Scheduling*.

## Included Components

| File | Purpose |
| :--- | :--- |
| [pipeline.py](pipeline.py) | Core CLI (`prepare`, `extract`, `seal`, `select-studies`, `model-check`, `assess`, `import-historical`, `export`, `finalize`) |
| [test_pipeline.py](test_pipeline.py) | Offline unit and regression test suite (`44` tests covering contiguous verification, numerical-omission/wrong-page/omitted-*never* rejection, split enforcement, resume identity, historical imports, manifest provenance preservation, and pre-call attempt/spending ceilings; 43 standalone tests including the portable synthetic fixture + 1 explicitly invoked integration test) |
| [audit_benchmark.py](audit_benchmark.py) | Programmatic audit recomputation and Markdown report generator (eliminates manual statistic transcription) |
| [build_provenance_manifest.py](build_provenance_manifest.py) | Raw provider cache, execution seal, retry, and `thoughts_token_count` provenance reconstructor |
| [build_review_packets.py](build_review_packets.py) | Generator for the isolated blind human review packet and evidence-grounded adjudication queue |
| [build_manuscript_docx.py](build_manuscript_docx.py) | Reproducible generator for `Pipeline_Methods_for_Manuscript_v0.3.0.docx` |
| [run_holdout.py](run_holdout.py) | Portable split-execution wrapper enforcing `--max-attempts`, `--max-cost-usd`, and explicit `--allow-api` authorisation |
| [models_source.yaml](models_source.yaml) | Pinned model identifiers, paid-tier token pricing, and token/timeout ceilings for `gemini-3.8-flash` and `gemini-4-argon` |
| [rubric_reference.json](rubric_reference.json) | Verbatim scoring rubric (`Table 4`) and exact `SG01`–`SG25` subgroup definitions |
| [VENDOR_PROVENANCE.json](VENDOR_PROVENANCE.json) | Upstream and delivered SHA-256 provenance for `vendor/*.py` and `models_source.yaml` |
| [MANIFEST.sha256](MANIFEST.sha256) | SHA-256 integrity manifest for the software files in the table above |

## Exclusions for Copyright & Blinding Integrity

To respect publisher copyright, API security, and human-review blinding, this archive excludes full-text publisher PDFs, marked-up Word manuscripts, raw provider caches, credentials, and private blind-review mapping keys (`work/review/private_keys/`). See [INPUTS.md](INPUTS.md) for local workspace layout.

## Citation Template

Costa, D., & Hosseini, M. R. (2026). *Gemini-Assisted Scoring of Building Deconstruction Research Evidence* (Version 0.3.0) [Computer software]. Faculty of Architecture, Building and Planning, The University of Melbourne.

The `supplement/` folder was added on 9 November 2026 for the manuscript. Those documents are not covered by `MANIFEST.sha256`.
