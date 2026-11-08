# Gemini-Assisted Scoring of Building Deconstruction Research Evidence

- **Software Version**: `0.3.0`
- **Package Date**: 8 November 2026
- **Active Repaired Sealed Hash**: `a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d`
- **Historical Holdout Benchmark Seal Audited**: `946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5`
- **Licence**: MIT

This repository provides the audited, reproducible multi-model evaluation and verification workflow developed for the systematic literature review (SLR) on *Digital Support for Building Deconstruction Sequencing and Scheduling* at the Faculty of Architecture, Building and Planning, The University of Melbourne.

## Key Capabilities in Version 0.3.0

1. **Contiguous Source-Text & Numeric-Boundary Verification (`pipeline.py`)**: Every supporting quotation for Scores `1`–`4` must match traceable, contiguous source text on the cited 1-based PDF page (`exact` or `normalized_contiguous`) or genuinely cross an adjacent page seam (`cross_page_contiguous`, with character-span provenance). Standalone number lines and digits are preserved across line breaks, and numeric token boundary checks block mid-number slicing, decimal/sign stripping, and `%` omission. Wrong-page attributions (`wrong_page`), contiguous kerning/ligature spacing artefacts (`uncertain_layout`), and omitted-word, numerical-omission, or spliced quotes (`unverified`) fail automated validation and route to human review.
2. **Preservation of Failed Assessments & Complete Review Routing**: Rejected batches are retained as `.rejected.json` records with subgroup-level diagnostics and exported into `comparison_*.csv` rather than silently excluded. All validation failures (`93/93` validation-failure pairs: `89` holdout pairs, `S05/SG05`, and `3` S06 pairs), disagreements (`94/94`), Score-4 candidates (`38/38`, including `S54/SG21` carrying `human_score_4`), and scope-flagged records (`25/25` for `S47`) are routed into `work/review/adjudication_queue.csv` (`188` rows: `161` holdout + `15` pilot + `12` S06 rows).
3. **Plan-Derived Split Selection, Resume Identity & Enforced Attempt/Cost Ceilings**: Study lists are generated directly from the sealed `plan.json` (`select-studies --split {calibration,holdout,production}`), rejecting unauthorized cross-split mixtures or altered split selections. Resumed runs verify `prompt_hash`, `model`, `model_settings`, and `source_pdf_sha256`. Live runs enforce pre-call and shared-ledger provider-attempt ceilings (`--max-attempts`) and worst-case pre-call USD reservation plus immediate post-response `usage_metadata` token settlement (`--max-cost-usd`, `--budget-file`), billing thinking tokens and truncated (`MAX_TOKENS`) responses.
4. **Cryptographic Provenance & Token Telemetry (`build_provenance_manifest.py`)**: Links all `210` retained batches (`180` historical holdout + `20` pilot + `10` S06 batches) and `242` raw provider responses (`219` unique request keys, `23` retries/reruns, `1` `MAX_TOKENS` response) to raw cache SHA-256 digests, original execution seals, and `usage_metadata.thoughts_token_count` / `cached_content_token_count`.
5. **Isolated Independent Human Review (`build_review_packets.py`)**: Builds a self-contained blind reviewer packet (`5` anonymised PDFs, verbatim rubric, exact `25` subgroup definitions, `125` blank rows; status `PENDING HUMAN COMPLETION`) strictly separated from private mapping keys, prior scores, and the supervisory adjudication queue.

## Quick Verification (Offline)

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -W default -m unittest -v test_pipeline.py
```

All **44 unit and regression tests** (43 standalone tests including the portable synthetic provenance regression + 1 explicitly invoked real-corpus integration test) execute offline without network access. Operational commands, budget reconciliation, and production hold controls are detailed in [RUNBOOK.md](RUNBOOK.md); academic methods and exact benchmark tables are documented in [METHODS.md](METHODS.md) and [VALIDATION.md](VALIDATION.md).

The 9 November 2026 manuscript supplement, agreement trace, and table reconciliation are in [supplement/](supplement/). This package has no Jupyter notebooks. Publisher full texts, sealed run caches, credentials, and the blind-review mapping are not included.
