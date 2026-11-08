# SLR Building Deconstruction: Scoring Pipeline Operational Runbook

- **Software Version**: `0.3.0`
- **Active Repaired Sealed Hash**: `a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d`
- **Historical Holdout Seal Audited**: `946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5`
- **Date**: 8 November 2026
- **Corpus Inventory**: `59` candidate studies $\times$ `25` subgroups (`1,475` study–subgroup pairs)
- **Eligible Synthesis Denominator**: `55` building-scope studies (`1,375` pairs; excluding `S47, S51, S55, S57`)
- **Operational Status**: **PRODUCTION ON HOLD** — zero new Gemini API calls may be executed without explicit written authorisation for a bounded pilot or split run.

## Table of Contents

1. [Environment & Integrity Verification](#1-environment--integrity-verification)
2. [Exact Scoring Rubric & Multi-Model Architecture](#2-exact-scoring-rubric--multi-model-architecture)
3. [Approved Split Selections & Scope Exclusions](#3-approved-split-selections--scope-exclusions)
4. [Historical Import, Remaining Work & Budget Reconciliation](#4-historical-import-remaining-work--budget-reconciliation)
5. [Human Review & Adjudication Workflows](#5-human-review--adjudication-workflows)
6. [CLI Execution Reference (Post-Authorisation)](#6-cli-execution-reference-post-authorisation)
7. [References](#7-references)

---

## 1. Environment & Integrity Verification

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Verify file checksums and run the offline unit/regression tests
shasum -a 256 -c MANIFEST.sha256
python -W default -m unittest -v test_pipeline.py
```

Verify the active sealed bundle (`a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d`) and inspect approved split lists without making any network requests:

```sh
.venv/bin/python pipeline.py select-studies --version a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d --split calibration --format json
.venv/bin/python pipeline.py select-studies --version a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d --split holdout --format json
.venv/bin/python pipeline.py select-studies --version a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d --split production --format json
```

---

## 2. Exact Scoring Rubric & Multi-Model Architecture

Every study–subgroup pair is assessed strictly against the author-supplied `Table 4` rubric (`Scoring criteria for assessing.docx` / [rubric_reference.json](rubric_reference.json)) across the exact 25 research-gap subgroups (`SG01`–`SG25`):

| Score | Exact Scoring Rule | Exact Evidence Required | Mandatory Pipeline Quote Roles |
| :--- | :--- | :--- | :--- |
| **`0 — Not relevant`** | The study does not discuss the specific gap or provide a contribution addressing it. | A full-text relevance check. Similar keywords alone are not sufficient. | Complete `pages_checked = [1..N]` |
| **`1 — Recognition only`** | The study identifies the gap but does not provide a contribution addressing it. | A direct quotation identifying the gap, with its page and section. | `gap` |
| **`2 — Contribution proposed`** | The study presents a method, framework, algorithm or data contribution addressing the gap but does not evaluate it. | A description of the contribution and how it relates to the gap. | `contribution` |
| **`3 — Contribution evaluated`** | The contribution is implemented and tested, but its performance is not checked against observations or data from an actual deconstruction project. | The evaluation method, test setting and results. Tests may use simulations or laboratory demonstrations. | `contribution`, `evaluation` |
| **`4 — Contribution evaluated using actual project observations`** | The contribution is implemented and tested against recorded observations or data from an actual deconstruction project. | The project-data source, measured information, evaluation method and results. | `contribution`, `evaluation`, `project` |

*(Note: Score `-1` is reserved for unresolved reading or visual-only evidence with `visual_evidence_needs_review: true` and is never collapsed into Score `0`. Score `4` strictly denotes evaluation against recorded observations or data from an actual deconstruction project—never a generic "practice-ready" label.)*

### Assessment Stages & Hard Budget Guards

- **`baseline` (`gemini-3.8-flash`)**: Uncalibrated zero-shot assessment (used in the exploratory holdout benchmark).
- **`flash` (`gemini-3.8-flash`)**: Few-shot assessment conditioned on source-verified PDF calibration examples from non-overlapping calibration families (`temperature=0`, `thinking_level=high`, `max_output_tokens=65,536`, serial concurrency `1`, max `4` attempts per request).
- **`argon` (`gemini-4-argon`)**: Independent blind assessment receiving only the original PDF, page-indexed text, exact rubric, and 5 subgroup definitions per batch (`temperature=0`, `thinking_level=high`, `max_output_tokens=65,536`, serial concurrency `1`, max `4` attempts per request).
- **Pre-Call Attempt & Spending Ceilings (`--max-attempts`, `--max-cost-usd`, `--budget-file`)**: Every live provider call (including retries) is gated prior to network transmission by `BudgetLedger` (`vendor/gemini.py`), reserving worst-case prompt + `max_output_tokens` USD cost before the call and settling exact `usage_metadata` tokens (including `thoughts_token_count` and truncated `MAX_TOKENS` responses) immediately upon receipt.

---

## 3. Approved Split Selections & Scope Exclusions

`pipeline.py assess` enforces exact plan-derived split membership and rejects cross-split mixtures or modified study lists (unless `--pilot-subset` is explicitly passed within a single split for an authorised pilot):

| Split | Total Studies | Eligible (`building_scope="yes"`) | Out-of-Scope (`building_scope="no"`) | Exact Approved Study IDs |
| :--- | :---: | :---: | :---: | :--- |
| **`calibration`** | 12 | 11 | 1 (`S51`) | `S01,S04,S08,S09,S10,S11,S17,S19,S20,S31,S49,S51` |
| **`holdout`** | 12 | 11 | 1 (`S47`) | `S02,S03,S14,S28,S29,S32,S45,S46,S47,S50,S53,S54` |
| **`production`** | 35 | 33 | 2 (`S55, S57`) | `S05,S06,S07,S12,S13,S15,S16,S18,S21,S22,S23,S24,S25,S26,S27,S30,S33,S34,S35,S36,S37,S38,S39,S40,S41,S42,S43,S44,S48,S52,S55,S56,S57,S58,S59` |
| **Total** | **59** | **55** | **4** | `S01`–`S59` |

- **Verified Out-of-Scope Exclusions (`N = 4`)**: `S47` (Tian et al., 2009, PDF pp. 1–5: mechanical fuzzy Petri net part disassembly), `S51` (Wang & Zhang, 2009, PDF pp. 1–4: mechanical disassembly-hive product planning), `S55` (Yu, 2012, PDF pp. 1–5: mechanical bearing/shaft-cover DfD planning), and `S57` (Zhang et al., 2020, PDF pp. 1, 7–13: stapler, gear pump, printer, and expander disassembly).
- **Verified Multi-Study Families (`N = 9`)**: `FAM_ANDRIYANI` (`S08,S09`, calibration); `FAM_MOTAHAR` (`S28,S29`, holdout), `FAM_SCHULTMANN` (`S45,S46`, holdout — three-storey domestic/residential masonry building in Mulhouse, `408 h` field baseline from Rentz et al., 1998), `FAM_YANG` (`S53,S54`, holdout); `FAM_ALLAM` (`S05–S07`, production), `FAM_JUVIGNY` (`S21,S22`, production), `FAM_KARSAN` (`S24,S56`, production), `FAM_SANCHEZ` (`S35–S43`, production), and `FAM_ZHONG` (`S58,S59`, production).
- **Special PDF Extraction Flag (`S56`)**: `Zain Karsan et al. - 2025` (`production`) has an embedded font missing a `ToUnicode` CMap (`ASCII - 31` shift in extracted text). Keep `S56` out of initial text-contiguity smoke pilots and route any `-1` / `uncertain_layout` / `unverified` items on `S56` to human visual PDF review.

---

## 4. Finalisation coverage snapshot

As of 9 November 2026, the active seal contains 99 accepted Flash/Argon batches: 73 historical holdout, 19 S05/S12 pilot, and 7 S06. Under the existing 590-batch requirement, 491 remain: 47 holdout, 120 calibration and 324 production. Recompute current counts from the active results before further work; do not treat this snapshot as a completed run. The private provenance manifest records 210 retained records (including rejected batches) and 242 raw provider responses.

### Lock the independent blind review after human completion

The independent reviewer completes all 125 rows in `work/review/blind_reviewer_packet/blind_reviewer_scoring_sheet.csv`, supplying a score 0–4 and a justification for each row. Before comparing with earlier ratings, the supervisor records the SHA-256 of that exact file in `work/review/private_keys/independent_review_status.json`, sets `locked` to `true`, and records the human reviewer in `completed_by` and the sign-off date/time in `locked_timestamp`. The status and private mapping must reference the active sealed version. Do not create these entries until a human has actually finished and signed the review. Editing the sheet after locking invalidates its hash and blocks finalisation. The separate 1,475-row human adjudication sheet and both complete model stages are also required by `pipeline.py finalize`.

---

## 5. Human Review & Adjudication Workflows

1. **Independent Blind Human Review (`PENDING HUMAN COMPLETION`)**:
   - Packet directory: `work/review/blind_reviewer_packet/` containing `pdfs/BLIND_STUDY_01.pdf`–`BLIND_STUDY_05.pdf`, `BLIND_REVIEWER_INSTRUCTIONS.md` (verbatim rubric + exact 25 subgroup definitions), and blank 125-row `blind_reviewer_scoring_sheet.csv`.
   - Strict isolation: Private mapping metadata and lock state (`work/review/private_keys/independent_review_status.json`, `locked: false`) and `adjudication_queue.csv` are kept strictly outside the reviewer packet.
   - Locking step: Before any comparison against Dulshan's scores or model outputs, compute `shasum -a 256 blind_reviewer_scoring_sheet.csv` and record the digest, reviewer identity, and timestamp in `independent_review_status.json`.
2. **Supervisory Adjudication Queue (`PENDING HUMAN SIGN-OFF`)**:
   - File: `work/review/adjudication_queue.csv` (`188` rows: `161` holdout + `15` pilot + `12` S06 rows).
   - Includes `90/90` validation-failure pairs (`88` holdout quote-failure pairs, `S02/SG10`, and `S05/SG05`), `94/94` three-way disagreements (classified into `0_vs_1_gap_recognition = 24`, `2_or_3_vs_4_project_observations = 12`, `0_vs_3_tested_contribution_scope = 31`, `other_intermediate_boundary = 27`), `38/38` Score-4 candidates (`S54/SG21` explicitly tagged `human_score_4|score_disagreement`), `25/25` `S47` scope rows, baseline differences, and `5` verified agreement controls.

---

## 6. CLI Execution Reference (Post-Authorisation)

### Rebuilding Offline Provenance, Imports, Exports, Review Packets & Audit Reports

```sh
SEAL="a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d"
HIST="946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5"

.venv/bin/python build_provenance_manifest.py --historical-version "$HIST" --target-version "$SEAL"
.venv/bin/python pipeline.py import-historical --from-version "$HIST" --to-version "$SEAL" --provenance work/provenance_manifest.json
.venv/bin/python pipeline.py export --version "$SEAL"
.venv/bin/python build_review_packets.py --version "$SEAL"
.venv/bin/python audit_benchmark.py --version "$SEAL"
```

### Bounded Technical Verification Pilot (Requires Explicit User Authorisation)

Enforces at most `20` total live provider attempts (including retries across both stages) and a hard `US$5.00` ceiling via a shared atomic ledger:

```sh
SEAL="a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d"
BUDGET="work/versions/$SEAL/pilot_S05_S12_budget.json"

.venv/bin/python pipeline.py assess --version "$SEAL" --stage flash --split production --pilot-subset --studies S05,S12 --max-calls 10 --max-attempts 20 --max-cost-usd 5.00 --budget-file "$BUDGET" --allow-api
.venv/bin/python pipeline.py assess --version "$SEAL" --stage argon --split production --pilot-subset --studies S05,S12 --max-calls 10 --max-attempts 20 --max-cost-usd 5.00 --budget-file "$BUDGET" --allow-api
.venv/bin/python pipeline.py export --version "$SEAL"
```

### Full Split Execution & Finalisation (Only After Pilot Gate & Adjudication Sign-Off)

```sh
SEAL="a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d"
PROD_BUDGET="work/versions/$SEAL/corpus_budget.json"

# Rescore the 47 rejected holdout batches (26 flash + 21 argon), then score calibration and production splits
.venv/bin/python pipeline.py assess --version "$SEAL" --stage flash --split holdout --retry-rejected --max-calls 26 --max-attempts 570 --max-cost-usd 100.00 --budget-file "$PROD_BUDGET" --allow-api
.venv/bin/python pipeline.py assess --version "$SEAL" --stage argon --split holdout --retry-rejected --max-calls 21 --max-attempts 570 --max-cost-usd 100.00 --budget-file "$PROD_BUDGET" --allow-api
.venv/bin/python pipeline.py assess --version "$SEAL" --stage flash --split calibration --max-calls 60 --max-attempts 570 --max-cost-usd 100.00 --budget-file "$PROD_BUDGET" --allow-api
.venv/bin/python pipeline.py assess --version "$SEAL" --stage argon --split calibration --max-calls 60 --max-attempts 570 --max-cost-usd 100.00 --budget-file "$PROD_BUDGET" --allow-api
.venv/bin/python pipeline.py assess --version "$SEAL" --stage flash --split production --max-calls 175 --max-attempts 570 --max-cost-usd 100.00 --budget-file "$PROD_BUDGET" --allow-api
.venv/bin/python pipeline.py assess --version "$SEAL" --stage argon --split production --max-calls 175 --max-attempts 570 --max-cost-usd 100.00 --budget-file "$PROD_BUDGET" --allow-api

.venv/bin/python pipeline.py export --version "$SEAL"
.venv/bin/python pipeline.py finalize --version "$SEAL" --review-sheet work/review/adjudicated_master.csv
```

---

## 7. References

- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46. *(Peer-reviewed source)*
- Google AI for Developers. (2026). *Gemini API documentation and pricing*. https://ai.google.dev/gemini-api/docs *(Vendor documentation)*
- Karsan, Z., Dillenburger, B., & De Wolf, C. (2025). Graph based disassembly sequencing with structural and stability constraints (`S56`). *(Peer-reviewed source)*
- Page, M. J., McKenzie, J. E., Bossuyt, P. M., Boutron, I., Hoffmann, T. C., Mulrow, C. D., ... & Moher, D. (2021). The PRISMA 2020 statement: An updated guideline for reporting systematic reviews. *BMJ*, 372, n71. https://doi.org/10.1136/bmj.n71 *(Peer-reviewed reporting standard)*
- Rentz, O., Ruch, M., Nicolai, M., Spengler, T., & Schultmann, F. (1998). *Selektiver Rückbau und Recycling von Gebäuden*. Landsberg: ecomed. *(Peer-reviewed / research monograph)*
- Schultmann, F., & Rentz, O. (2001). Environment-oriented project scheduling for the dismantling of buildings. *OR Spektrum*, 23, 51–78 (`S45`). *(Peer-reviewed source)*
- Schultmann, F., & Rentz, O. (2002). Scheduling of deconstruction projects under resource constraints. *Construction Management and Economics*, 20(5), 391–401 (`S46`). *(Peer-reviewed source)*
- Tian, Y., Wang, T. Y., Ding, B. H., He, G. Y., & Zheng, H. J. (2009). Research on modularization fuzzy Petri net of disassembly system (`S47`). *(Peer-reviewed source)*
- Wang, W., & Zhang, J. (2009). Study on multi-dimensional disassembly planning strategy based on disassembly hive (`S51`). *(Peer-reviewed source)*
- Yu, Y. Z. (2012). Research on disassembly sequence planning in DFD (`S55`). *(Peer-reviewed source)*
- Zhang, N., Liu, Z., Qiu, C., Cheng, J., & Tan, J. (2020). Disassembly sequence planning using a fast and effective precedence-based disassembly subset-generation method. *Proceedings of the Institution of Mechanical Engineers, Part B: Journal of Engineering Manufacture*, 234(3), 513–526 (`S57`). *(Peer-reviewed source)*
