# Pipeline Validation, Revalidation & Verification Record

- **Software Version**: `0.3.0`
- **Verification Date**: 8 November 2026
- **Active Repaired Sealed Hash**: `a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d`
- **Historical Holdout Seal Audited**: `946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5`
- **Runtime Environment**: macOS, Python `3.12.12` virtual environment (`.venv`), `PyMuPDF 1.26.5`, `google-genai 1.47.0`, `jsonschema 4.25.1`

---

## 1. Offline Unit & Regression Suite (`38` Tests Passing)

Running `python -W default -m unittest -v test_pipeline.py` executes **38 deterministic offline tests** in `< 1 s` with zero warnings and zero network calls:

| Test Group | Key Regression Coverage |
| :--- | :--- |
| **Contiguous Quotation & Numeric-Boundary Verification** | Accepts `exact`, `normalized_contiguous` (Unicode NFKC, soft-hyphen/line-break join, and whitespace folding while strictly preserving standalone number lines and digits), and genuine `cross_page_contiguous` spans (`idx < boundary_a` and `end > boundary_b` with `char_spans`). `test_numerical_omissions_and_truncations_blocked` blocks standalone line-wrapped integer omissions (`408`, `801`), mid-number slicing (`408` → `8` / `40`), decimal/sign slicing (`0.25%` → `25%`, `-15%` → `15%`), and `%` omission. |
| **Rejection of Distorted & Misattributed Quotes** | `test_omitted_never_reversing_meaning_rejected` rejects quotes omitting *"never"*; `test_wrong_page_quote_rejected_including_adjacent_page` rejects quotes attributed to the wrong page (including adjacent pages); `test_spliced_sentences_rejected` confirms removal of the 400-character gap bridge and 80% word-bag heuristic; `test_uncertain_layout_routed_to_review_not_accepted` routes PDF kerning/ligature spacing artefacts (`uncertain_layout`) to human review. |
| **Plan, Split & Prompt Isolation** | `test_plan_valid_and_non_mutating` verifies non-mutating calibration validation; `test_approved_production_selection_and_rejection` confirms exact split lists (`calibration=12`, `holdout=12`, `production=35`, with `S55, S57` excluded in production and `S51` in calibration) and rejects altered or cross-split lists; Argon prompts remain strictly blind. |
| **Resume Identity & Historical Import** | `test_resume_validates_prompt_and_config_identities` blocks silent reuse when `prompt_hash` or `model_settings` drift; `test_historical_import_preserves_original_seal_and_failed_assessments` verifies preservation of `original_execution_seal`, `.rejected.json` reviewable records, and `human_score_4` flags. |
| **Enforced Provider-Attempt & Spending Ceilings** | `test_excess_provider_attempts_blocked_during_retries` and `test_excess_provider_attempts_blocked_across_stages_via_shared_budget_file` verify pre-call blocking of excess retries and cross-stage provider attempts (`--max-attempts`, `--budget-file`); `test_excess_spending_blocked_pre_call_and_bills_thinking_and_truncated_responses` verifies worst-case pre-call USD reservation blocking (`--max-cost-usd`) and immediate billing of `thoughts_token_count` and truncated `MAX_TOKENS` responses. |

---

## 2. Repaired Historical Revalidation & Queue Completeness (`1,800` Quotations)

Revalidating all `180` historical holdout batches (`60 baseline`, `60 flash`, `60 argon` across `300` study–subgroup pairs) under `a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d` via `import-historical`, `export` (`comparison_9cc23fc8b615.csv`), and `audit_benchmark.py` produced:

- **Passing contiguous quotations**: **`1,561 / 1,800` (`86.72%`)** — `exact = 15`, `normalized_contiguous = 1,546`, `cross_page_contiguous = 0`.
- **Rejected / review-routed quotations**: **`239 / 1,800` (`13.28%`)** — `uncertain_layout = 62` (`25` baseline, `19` flash, `18` argon), `wrong_page = 3` (`2` baseline, `1` flash, `0` argon), `unverified = 174` (`39` baseline, `54` flash, `81` argon; includes `S54` author-manuscript margin line-number interruptions preserved after removing standalone digit-line stripping).
- **Affected study–subgroup pairs**: **`88` distinct `(study_id, subgroup)` pairs** have at least one non-passing quotation (`44` baseline, `57` flash, `36` argon), plus **`1` pair (`S02/SG10`)** failing the required evidence-role check = **`89` total validation-failure pairs**.
- **Review queue coverage (`work/review/adjudication_queue.csv`, `161` rows)**: Covers **`89 / 89` (`100%`, `0` missing)** validation-failure pairs, **`94 / 94`** three-way disagreements, **`38 / 38`** Score-4 candidate pairs (including `S54/SG21` carrying `human_score_4|score_disagreement`), **`25 / 25`** out-of-scope `S47` pairs, baseline stage differences, and `5` verified agreement controls.

---

## 3. Exploratory Holdout Benchmark Summary (`N = 300` Pairs)

Computed directly from `work/audit/benchmark_recomputation_audit.json` via `audit_benchmark.py`:

- **Full holdout (`N = 300`)**: Baseline Flash exact `237/300 (79.00%)`, MAE `0.4800`, $\kappa =$ **`0.5845`**; Calibrated Flash exact `230/300 (76.67%)`, MAE `0.5233`, $\kappa =$ **`0.5525`**; Blind Argon exact `228/300 (76.00%)`, MAE `0.5100`, $\kappa =$ **`0.5846`**; Flash–Argon $\kappa =$ **`0.6804`** (`244/300 = 81.33%`); three-way exact consensus `206/300 (68.67%)`; disagreements `94/300 (31.33%)`.
- **Eligible building-scope subset (`N = 275`, excluding `S47`)**: Baseline Flash $\kappa = 0.6014$ (`217/275`), Calibrated Flash $\kappa = 0.5717$ (`211/275`), Blind Argon $\kappa = 0.6154$ (`212/275`), Flash–Argon $\kappa =$ **`0.6814`** (`223/275`), three-way consensus `190/275 (69.09%)`, disagreements `85/275`.
- **Non-zero reference subset (`N = 100`, `Dulshan > 0`)**: Baseline Flash exact `57/100`, MAE `0.9600`, $\kappa = 0.3993$; Calibrated Flash exact `57/100`, MAE `0.9900`, $\kappa = 0.3997$; Blind Argon exact `71/100`, MAE `0.5000`, $\kappa = 0.5597$.
- **Disagreement taxonomy (`N = 94`)**: `0_vs_1_gap_recognition = 24`, `2_or_3_vs_4_project_observations = 12`, `0_vs_3_tested_contribution_scope = 31`, `other_intermediate_boundary = 27`.
- **Baseline Score-4 check**: `S45/SG03 = 2` and `S54/SG03 = 2`.
- **Exploratory status**: This 12-study comparison against a single human rater is exploratory and provides **no evidence of calibration improvement**.

---

## 4. Documented Limitations & Current Hold Controls

1. **Pending Human Reviews**: Independent blind human scoring (`work/review/blind_reviewer_packet/`, `125` blank rows across `5` anonymised PDFs) is **`PENDING HUMAN COMPLETION`** (`locked: false`). Supervisory adjudication (`work/review/adjudication_queue.csv`, `188` queued items) is likewise **`PENDING HUMAN SIGN-OFF`**. `pipeline.py finalize` blocks synthesis generation until all required reviews and batch coverages are complete.
2. **Embedded PDF Font CMap Defect in `S56`**: Corpus-wide extraction auditing identified that production study `S56` (*Karsan et al., 2025*) uses an embedded font without a valid `ToUnicode` CMap, shifting extracted characters by `ASCII - 31` while vector PDF rendering remains legible. `S56` is flagged in `plan.json` so unextractable passages use `-1` / `visual_evidence_needs_review: true` and route to human visual inspection.
3. **Production status**: The S05/S12 technical pilot and S06 provisional scoring have run. Additional scoring requires the operator to follow the approved plan; final synthesis requires the completed blind-review lock and adjudication.

---

## References

- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46. *(Peer-reviewed source)*
- Karsan, Z., Dillenburger, B., & De Wolf, C. (2025). Graph based disassembly sequencing with structural and stability constraints (`S56`). *(Peer-reviewed source)*
- PyMuPDF Development Team. (2026). *PyMuPDF documentation* (Version 1.26.5). Artifex Software, Inc. https://pymupdf.readthedocs.io/ *(Software documentation)*
