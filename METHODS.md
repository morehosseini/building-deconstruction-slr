# Evidence-Grounded Multi-Model Triangulation and Contiguous Quotation Verification for Systematic Literature Reviews

- **Subtitle**: Methods Text and Technical Specification for the Systematic Literature Review of Digital Support for Building Deconstruction Sequencing and Scheduling
- **Software Version**: `0.3.0` (8 November 2026)
- **Active Repaired Sealed Hash**: `a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d`
- **Historical Holdout Seal Audited**: `946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5`
- **Authors**: Dulshan Costa & Dr M. Reza Hosseini
- **Affiliation**: Faculty of Architecture, Building and Planning, The University of Melbourne

## Table of Contents

1. [Assessment Design, Exact Scoring Rubric, and Subgroup Definitions](#1-assessment-design-exact-scoring-rubric-and-subgroup-definitions)
2. [PRISMA Scope Reconciliation, Family Partition, and Synthesis Denominator](#2-prisma-scope-reconciliation-family-partition-and-synthesis-denominator)
3. [Document Extraction, Multimodal Delivery, and Contiguous Quotation Verification](#3-document-extraction-multimodal-delivery-and-contiguous-quotation-verification)
4. [Multi-Model Triangulation Architecture and Provenance Controls](#4-multi-model-triangulation-architecture-and-provenance-controls)
5. [Exploratory Holdout Benchmark Audit (`N = 300` Pairs)](#5-exploratory-holdout-benchmark-audit-n--300-pairs)
6. [Independent Human Review and Evidence-Grounded Adjudication](#6-independent-human-review-and-evidence-grounded-adjudication)
7. [Historical Import Reconciliation, Remaining Coverage, and Token Budget](#7-historical-import-reconciliation-remaining-coverage-and-token-budget)
8. [Technical Specification Tables (Tables S1–S4)](#8-technical-specification-tables-tables-s1s4)
9. [References](#9-references)

---

## 1. Assessment Design, Exact Scoring Rubric, and Subgroup Definitions

To evaluate the evidentiary maturity of digital methods for building deconstruction sequencing and scheduling, the candidate corpus (`59` retrieved publications, `S01`–`S59`) is assessed across the exact `25` research-gap subgroups (`SG01`–`SG25`) defined in the review protocol (`59 × 25 = 1,475` study–subgroup pairs). Each study–subgroup pair is scored on the author's verbatim five-level ordinal scale (`0`–`4`) extracted directly from `Scoring criteria for assessing.docx` (Table S3) and paired with the exact shared research requirement from `Sub group Scoring 0-4.xlsx` (Table S4).

Critically, **Score 4** (*"Contribution evaluated using actual project observations"*) is strictly an empirical evidence-source classification requiring that the subgroup contribution be implemented and tested against recorded observations or data from an actual deconstruction project; it is never interpreted as a generic *"practice-ready"* quality endorsement (the phrase *"practice-ready"* appears solely within the verbatim requirement title of subgroup `SG15`). Where decisive evidence is contained exclusively in unextractable figures or corrupted font layers, the machine pipeline records sentinel score `-1` with `visual_evidence_needs_review = true` rather than substituting Score `0`.

---

## 2. PRISMA Scope Reconciliation, Family Partition, and Synthesis Denominator

Full-text eligibility verification against original PDFs (Page et al., 2021) reconciled the `59`-record workbook inventory to **`N = 55` eligible building-scope studies** (`1,375` study–subgroup pairs) and **`N = 4` excluded out-of-scope mechanical/product disassembly studies** (`100` pairs):

1. **`S47` (Tian et al., 2009; `holdout`, PDF pp. 1–5)**: Generic mechanical manufacturing fuzzy Petri net product/part disassembly model (parts 2, 3, 4, 8; RMB/s factory operator salary), with zero building or civil structures.
2. **`S51` (Wang & Zhang, 2009; `calibration`, PDF pp. 1–4)**: Mechanical engineering disassembly-hive / disassembly-ring product part planning (airproof space, machining surface roughness, mechanism velocity), with zero building application.
3. **`S55` (Yu, 2012; `production`, PDF pp. 1–5)**: Mechanical product Design for Disassembly (DfD) sequence planning demonstrated on bearing and shaft-cover subassemblies (Fig. 2, Fig. 4, p. 3), with zero building structures.
4. **`S57` (Zhang et al., 2020; `production`, PDF pp. 1, 7–13)**: Manufacturing end-of-life product disassembly subset-generation tested on an 18-part stapler, 20-part hydraulic gear pump, 52-part printer (pp. 9–11), and 13-part industrial expander (p. 12), with zero building scope.

All `59` records remain in the sealed audit inventory for complete provenance, while `pipeline.py finalize` restricts subgroup synthesis denominators strictly to the `N = 55` studies with `building_scope = "yes"`.

To prevent cross-split leakage from overlapping authorship or shared empirical case data, all `59` records are partitioned by study family (`9` multi-study families plus `33` singleton families in `plan.json`, `42` families in total) across `calibration` (`12` studies; `S51` out-of-scope), `holdout` (`12` studies; `S47` out-of-scope), and `production` (`35` studies; `S55, S57` out-of-scope). In particular, `FAM_SCHULTMANN` groups `S45` (Schultmann & Rentz, 2001) and `S46` (Schultmann & Rentz, 2002) within `holdout`: inspection of the original PDFs (`S45` pp. 1, 6, 8, 15, 17; `S46` pp. 1, 3, 6, 9–10) confirms that both articles evaluate multi-mode resource-constrained dismantling schedules on a **three-storey domestic/residential masonry building** (Mulhouse dwelling-house, `408 h` field baseline from Rentz et al., 1998), comparing simulated dismantling Scenarios 1–3 (`221 h`, `165 h`, `185 h`) against that practical baseline.

---

## 3. Document Extraction, Multimodal Delivery, and Contiguous Quotation Verification

Original PDFs are extracted locally via PyMuPDF (`1.26.5`) in natural reading flow (`page.get_text("text")`) and transmitted alongside the complete raw PDF bytes (`application/pdf`) so multimodal models inspect architectural drawings, tables, and schedules alongside 1-based `[PDF PAGE p]` text. Corpus-wide PDF inspection identified one production article (`S56`, Karsan et al., 2025, PDF pp. 1–7) whose embedded font lacks a `ToUnicode` CMap (`ASCII - 31` character shift in extracted text while vector PDF rendering remains legible); `S56` is explicitly flagged in `plan.json` for visual review routing.

To prevent fabricated, paraphrased, misattributed, numerically truncated, or spliced quotations from passing automated checks, `verify_evidence_contiguous` enforces strict contiguous source-text and numeric-boundary matching:

- **Accepted contiguous statuses**:
  1. `exact`: Verbatim substring match on the cited 1-based PDF page satisfying numeric token boundary integrity (`_valid_numeric_boundaries`), recording exact `[start, end)` character offsets.
  2. `normalized_contiguous`: Contiguous substring match on the cited page after Unicode NFKC normalisation, typographic quote/dash standardisation, end-of-line soft-hyphen repair, and whitespace folding—strictly preserving all standalone number lines and digits across line breaks and enforcing numeric token boundaries so mid-number slicing, decimal/sign stripping, `%` omissions, or skipped words cannot pass.
  3. `cross_page_contiguous`: Contiguous match across `[p-1, p]` or `[p, p+1]` verified to be absent from either single page alone and to genuinely cross the inter-page boundary (`idx < boundary_a` and `end > boundary_b`), recording per-page character spans.
- **Rejected diagnostic statuses (routed to human review)**:
  - `wrong_page`: Contiguous match exists on a different page of the same PDF (including an adjacent page when the quote does not cross the page seam).
  - `uncertain_layout`: Contiguous alphanumeric sequence matches on the cited page (`len >= 12`) with valid numeric boundaries, where whitespace or ligature kerning differs from standard layout normalisation.
  - `unverified`, `too_short`, `page_out_of_bounds`: Any omitted word (e.g., omitting *"never"* and reversing source polarity), omitted or truncated number, non-contiguous splice, paraphrase, or invalid page index.

All previously permissive fallbacks (80% word-bag matching, `"we propose"` keyword checks, 400-character gap bridges, and standalone digit-line stripping) are removed. Batches with any validation failure are preserved as reviewable `.rejected.json` records with subgroup-level diagnostics and exported into `comparison_*.csv` with explicit `<stage>_status` and `review_flags`.

---

## 4. Multi-Model Triangulation Architecture and Provenance Controls

Each study (`25` subgroups) is evaluated in `5` sequential batches of `5` subgroups under deterministic decoding (`temperature = 0.0`, `thinking_level = "high"`, `max_output_tokens = 65,536`, serial concurrency `1`):

1. **Baseline Flash (`gemini-3.8-flash`)**: Uncalibrated zero-shot assessment (used in the exploratory holdout benchmark).
2. **Calibrated Flash (`gemini-3.8-flash`)**: Few-shot assessment receiving source-verified calibration examples from `plan.json` while excluding any example from the target study's `family_id`.
3. **Blind Argon (`gemini-4-argon`)**: Independent frontier assessment receiving only the PDF, page-indexed text, verbatim rubric, and target subgroup definitions, with zero calibration examples or cross-model visibility.

`pipeline.py` enforces sealed bundle verification (`code_identity()`, `runtime_identity()`, and SHA-256 checks on all `59` PDFs and authority files), plan-derived split selection (`select-studies` / `resolve_requested_studies`), resume identity checks (`prompt_hash`, `model`, `model_settings`, and `source_pdf_sha256`), and hard pre-call provider-attempt and USD spending ceilings (`BudgetLedger` in `vendor/gemini.py`, reserving worst-case prompt + `max_output_tokens` cost prior to every attempt and immediately settling `usage_metadata` tokens—including thinking and `MAX_TOKENS` responses—upon receipt). `build_provenance_manifest.py` links every retained batch, rejected record, and retry to its request cache key, original execution seal, raw provider JSON SHA-256, `response_id`, `finish_reason`, and token telemetry including `usage_metadata.thoughts_token_count` and `cached_content_token_count`.

---

## 5. Exploratory Holdout Benchmark Audit (`N = 300` Pairs)

All holdout statistics are computed programmatically from `comparison_9cc23fc8b615.csv` and `work/audit/benchmark_recomputation_audit.json` via `audit_benchmark.py`. This 12-study (`300`-pair) evaluation is an **exploratory single-reference benchmark** against Dulshan Costa's initial coding and **provides no evidence of calibration improvement**: Calibrated Flash ($\kappa = 0.5525$) achieved slightly lower agreement with Dulshan's reference scores than uncalibrated Baseline Flash ($\kappa = 0.5845$), while uncalibrated Blind Argon achieved $\kappa = 0.5846$.

### Summary of Exploratory Agreement Metrics

| Subset & Rater Stage | Exact Match | Within $\pm 1$ Point | MAE | Unweighted Cohen's $\kappa$ | Score-4 Recall | Score-4 Precision |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Full Holdout (`N = 300`) — Baseline Flash** | 237/300 (79.00%) | 258/300 (86.00%) | 0.4800 | **0.5845** | 10/19 (52.63%) | 10/20 (50.00%) |
| **Full Holdout (`N = 300`) — Calibrated Flash** | 230/300 (76.67%) | 254/300 (84.67%) | 0.5233 | **0.5525** | 10/19 (52.63%) | 10/19 (52.63%) |
| **Full Holdout (`N = 300`) — Blind Argon** | 228/300 (76.00%) | 258/300 (86.00%) | 0.5100 | **0.5846** | 18/19 (94.74%) | 18/37 (48.65%) |
| **Eligible Only (`N = 275`, excl. `S47`) — Baseline Flash** | 217/275 (78.91%) | 238/275 (86.55%) | 0.4691 | **0.6014** | 10/19 (52.63%) | 10/20 (50.00%) |
| **Eligible Only (`N = 275`, excl. `S47`) — Calibrated Flash** | 211/275 (76.73%) | 235/275 (85.45%) | 0.5091 | **0.5717** | 10/19 (52.63%) | 10/19 (52.63%) |
| **Eligible Only (`N = 275`, excl. `S47`) — Blind Argon** | 212/275 (77.09%) | 242/275 (88.00%) | 0.4582 | **0.6154** | 18/19 (94.74%) | 18/37 (48.65%) |
| **Non-Zero Reference (`N = 100`, `Dulshan > 0`) — Baseline Flash** | 57/100 (57.00%) | 70/100 (70.00%) | 0.9600 | **0.3993** | 10/19 (52.63%) | 10/16 (62.50%) |
| **Non-Zero Reference (`N = 100`, `Dulshan > 0`) — Calibrated Flash** | 57/100 (57.00%) | 68/100 (68.00%) | 0.9900 | **0.3997** | 10/19 (52.63%) | 10/15 (66.67%) |
| **Non-Zero Reference (`N = 100`, `Dulshan > 0`) — Blind Argon** | 71/100 (71.00%) | 85/100 (85.00%) | 0.5000 | **0.5597** | 18/19 (94.74%) | 18/31 (58.06%) |

- **Inter-model agreement (`Calibrated Flash` vs `Blind Argon`)**: $\kappa = \mathbf{0.6804}$ (`244/300 = 81.33%`) on the full holdout set, and $\kappa = \mathbf{0.6814}$ (`223/275 = 81.09%`) on the eligible building-scope subset (`N = 275`).
- **Three-way consensus (`Dulshan == Calibrated Flash == Blind Argon`)**: `206/300` (`68.67%`) overall (`94` disagreements), and `190/275` (`69.09%`) on eligible studies (`85` disagreements).
- **Baseline Score-4 verification**: Baseline Flash scored `2` on both `S45/SG03` and `S54/SG03`.

### Descriptive Disagreement Taxonomy (`N = 94` Three-Way Disagreements)

Let $V = \{\text{Dulshan}, \text{Calibrated Flash}, \text{Blind Argon}\} $ for each holdout pair with $|V| > 1$:

| Category | Formal Set Definition on $V = \{H, F, A\}$ | Count | Percentage |
| :--- | :--- | :---: | :---: |
| `0_vs_1_gap_recognition` | $|V| > 1$ and $V \subseteq \{0, 1\}$ | **24** | 25.53% |
| `2_or_3_vs_4_project_observations` | $|V| > 1$, $4 \in V$, and $V \cap \{2, 3\} \neq \emptyset$ | **12** | 12.77% |
| `0_vs_3_tested_contribution_scope` | $\{0, 3\} \subseteq V$ and $4 \notin V$ | **31** | 32.98% |
| `other_intermediate_boundary` | All remaining pairs with $|V| > 1$ not matching the three predicates above | **27** | 28.72% |
| **Total** | **All three-way holdout disagreements** | **94** | **100.00%** |

### Repaired Quotation Revalidation Across `1,800` Holdout Quotations

Across the `180` historical batches (`1,800` evidence quotations), **`1,561/1,800` (`86.72%`)** matched contiguously (`exact = 15`, `normalized_contiguous = 1,546`, `cross_page_contiguous = 0`), and **`239/1,800` (`13.28%`)** were rejected and routed to review (`uncertain_layout = 62`, `wrong_page = 3`, `unverified = 174`, including `S54` author-manuscript margin line-number interruptions preserved after removing standalone digit-line stripping), affecting **`88` distinct `(study_id, subgroup)` pairs** plus **`1` role-only failure pair (`S02/SG10`)** = **`89` total validation-failure pairs**.

---

## 6. Independent Human Review and Evidence-Grounded Adjudication

1. **Independent Blind Human Review (`PENDING HUMAN COMPLETION`)**: `build_review_packets.py` constructs `work/review/blind_reviewer_packet/` containing five anonymised original PDFs (`pdfs/BLIND_STUDY_01.pdf`–`05.pdf`), `BLIND_REVIEWER_INSTRUCTIONS.md` (verbatim rubric and exact `25` subgroup definitions), and a blank `125`-row scoring sheet (`blind_reviewer_scoring_sheet.csv`). Private mapping records and lock state (`work/review/private_keys/independent_review_status.json`, `status = "pending_human_completion"`, `locked = false`) and `adjudication_queue.csv` are excluded from the reviewer packet. Independent human scores must be completed and cryptographically locked via SHA-256 prior to unblinding or comparison.
2. **Supervisory Adjudication Queue (`PENDING HUMAN SIGN-OFF`)**: `work/review/adjudication_queue.csv` (`188` rows: `161` holdout + `15` pilot + `12` S06 rows) captures `93/93` validation-failure pairs (`0` missing), `94/94` three-way disagreements, `38/38` Score-4 candidates (including `S54/SG21` explicitly tagged `human_score_4|score_disagreement`), `25/25` `S47` out-of-scope rows, baseline differences, and `5` verified agreement controls. Adjudication notes and candidate proposals are grounded in direct PDF and workbook inspection (for example, `S46/SG10` PDF p. 9 explicitly disclaims algorithmic efficiency development and reports suboptimal solutions in 25% of cases, refuting Argon's Score 4; `S54/SG21` PDF pp. 21, 31, 40 contrasts empirical documentation of forced MEP removal vs bolted joint release against planning-method requirements, routed as `NEEDS_HUMAN_DETERMINATION`).

---

## 7. Historical Import Reconciliation, Remaining Coverage, and Token Budget

To satisfy `pipeline.py finalize` coverage across all `59` studies (`59 × 5 × 2 = 590` `flash` + `argon` batches):

- **Coverage snapshot (9 November 2026)**: 99 Flash/Argon batches are accepted: 73 holdout, 19 pilot and 7 S06. The 590-batch finalisation gate therefore has 491 outstanding: 47 holdout, 120 calibration and 324 production. All model scores remain provisional.
- **Without historical imports**: Scoring all `59` studies from scratch requires **`590` successful requests** (`295 flash + 295 argon`), plus retries.
- **Execution accounting**: The historical holdout comprised 180 retained batches and 212 raw provider responses. The current private manifest contains 210 retained batches and 242 raw responses, including the pilot and S06. These are dated snapshots and will change as scoring continues.

---

## 8. Technical Specification Tables (Tables S1–S4)

### Table S1: Effective Model and Execution Configuration (`models_source.yaml` + `model_config()`)

| Parameter | Baseline & Calibrated Flash | Blind Argon |
| :--- | :---: | :---: |
| **Model Identifier** | `gemini-3.8-flash` | `gemini-4-argon` |
| **Thinking Level** | `high` | `high` |
| **Temperature** | `0.0` | `0.0` |
| **Maximum Output Tokens** | `65,536` | `65,536` |
| **Request Timeout** | `600 s` | `1,200 s` |
| **Effective Max Attempts (`model_config`)** | `4` | `4` |
| **Effective Concurrency (`model_config`)** | `1` (serial) | `1` (serial) |
| **Subgroups per Batch Request** | `5` (`5` batches/study) | `5` (`5` batches/study) |
| **Rate-Limit Ceiling (`models_source.yaml`)** | `1,800 RPM / 2,700,000 TPM` | `120 RPM / 1,000,000 TPM` |

### Table S2: Pinned Software Dependencies (`requirements.txt`)

| Package | Version | Role |
| :--- | :---: | :--- |
| `google-genai` | `1.47.0` | Multimodal Gemini API transport and structured schema enforcement |
| `PyMuPDF` | `1.26.5` | Local PDF SHA-256 verification and page-indexed text extraction |
| `PyYAML` | `6.0.3` | Model configuration parsing |
| `openpyxl` | `3.1.5` | Read-only parsing of `Sub group Scoring 0-4.xlsx` |
| `jsonschema` | `4.25.1` | Strict local JSON Schema validation (`additionalProperties: false`) |

### Table S3: Verbatim Scoring Rubric (`Scoring criteria for assessing.docx`, Table 4)

| Score | Scoring rule | Evidence required |
| :--- | :--- | :--- |
| `0 — Not relevant` | The study does not discuss the specific gap or provide a contribution addressing it. | A full-text relevance check. Similar keywords alone are not sufficient. |
| `1 — Recognition only` | The study identifies the gap but does not provide a contribution addressing it. | A direct quotation identifying the gap, with its page and section. |
| `2 — Contribution proposed` | The study presents a method, framework, algorithm or data contribution addressing the gap but does not evaluate it. | A description of the contribution and how it relates to the gap. |
| `3 — Contribution evaluated` | The contribution is implemented and tested, but its performance is not checked against observations or data from an actual deconstruction project. | The evaluation method, test setting and results. Tests may use simulations or laboratory demonstrations. |
| `4 — Contribution evaluated using actual project observations` | The contribution is implemented and tested against recorded observations or data from an actual deconstruction project. | The project-data source, measured information, evaluation method and results. |

### Table S4: Exact 25 Research-Gap Subgroup Definitions (`rubric_reference.json`)

| Subgroup | Exact Shared Research Requirement |
| :--- | :--- |
| `SG01` | Automating disassembly model preparation |
| `SG02` | Incomplete or insufficiently detailed building models |
| `SG03` | Reliable empirical planning data |
| `SG04` | Economic and environmental objectives in selective planning |
| `SG05` | Resources, equipment and site constraints |
| `SG06` | Extension to complete and complex buildings |
| `SG07` | Connecting sequence planning with robotic execution |
| `SG08` | Representing dependencies and component completeness |
| `SG09` | Structural stability during removal |
| `SG10` | Optimisation quality and computational scalability |
| `SG11` | Disassembly information standards and taxonomies |
| `SG12` | Interoperability and data requirements across digital tools |
| `SG13` | Capturing practitioners' knowledge in ontologies |
| `SG14` | Immersive visualisation for recovery and reuse planning |
| `SG15` | Developing automated and practice-ready planning workflows |
| `SG16` | Field validation and evidence across building contexts |
| `SG17` | Robotic perception and adaptation to site conditions |
| `SG18` | Coordinating robots and human workers |
| `SG19` | Enriching voxel models with lifecycle and structural data |
| `SG20` | Early project decisions for circular delivery |
| `SG21` | Alternative dismantling techniques in planning |
| `SG22` | Modular disassembly and complex extraction paths |
| `SG23` | Scheduling under uncertainty and weak data |
| `SG24` | Sensor-based acquisition and semantic BIM generation |
| `SG25` | Connection lock-in stress affecting disassembly |

---

## 9. References

- Akl, J., Pericherla, S., & Calli, B. (2023). Cut sequencing algorithm for safely disassembling large structures (`S02`). *(Peer-reviewed source)*
- Cohen, J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37–46. *(Peer-reviewed source)*
- Google AI for Developers. (2026). *Gemini API models and pricing documentation*. https://ai.google.dev/gemini-api/docs *(Vendor documentation)*
- Karsan, Z., Dillenburger, B., & De Wolf, C. (2025). Graph based disassembly sequencing with structural and stability constraints (`S56`). *(Peer-reviewed source)*
- Page, M. J., McKenzie, J. E., Bossuyt, P. M., Boutron, I., Hoffmann, T. C., Mulrow, C. D., ... & Moher, D. (2021). The PRISMA 2020 statement: An updated guideline for reporting systematic reviews. *BMJ*, 372, n71. https://doi.org/10.1136/bmj.n71 *(Peer-reviewed reporting standard)*
- PyMuPDF Development Team. (2026). *PyMuPDF documentation* (Version 1.26.5). Artifex Software, Inc. https://pymupdf.readthedocs.io/ *(Software documentation)*
- Rentz, O., Ruch, M., Nicolai, M., Spengler, T., & Schultmann, F. (1998). *Selektiver Rückbau und Recycling von Gebäuden*. Landsberg: ecomed. *(Research monograph)*
- Schultmann, F., & Rentz, O. (2001). Environment-oriented project scheduling for the dismantling of buildings. *OR Spektrum*, 23, 51–78 (`S45`). *(Peer-reviewed source)*
- Schultmann, F., & Rentz, O. (2002). Scheduling of deconstruction projects under resource constraints. *Construction Management and Economics*, 20(5), 391–401 (`S46`). *(Peer-reviewed source)*
- Tian, Y., Wang, T. Y., Ding, B. H., He, G. Y., & Zheng, H. J. (2009). Research on modularization fuzzy Petri net of disassembly system (`S47`). *(Peer-reviewed source)*
- Volk, R., Luu, T. H., Mueller-Roemer, J. S., Sevilmis, N., & Schultmann, F. (2018). Deconstruction project planning of existing buildings based on automated acquisition and reconstruction of building information. *Automation in Construction*, 91, 226–245 (`S50`). *(Peer-reviewed source)*
- Wang, W., & Zhang, J. (2009). Study on multi-dimensional disassembly planning strategy based on disassembly hive (`S51`). *(Peer-reviewed source)*
- Yang, Y., Luk, C., et al. (2025). Disassembly and reuse of demountable modular building systems (`S54`). *(Peer-reviewed source)*
- Yu, Y. Z. (2012). Research on disassembly sequence planning in DFD (`S55`). *(Peer-reviewed source)*
- Zhang, N., Liu, Z., Qiu, C., Cheng, J., & Tan, J. (2020). Disassembly sequence planning using a fast and effective precedence-based disassembly subset-generation method. *Proceedings of the Institution of Mechanical Engineers, Part B: Journal of Engineering Manufacture*, 234(3), 513–526 (`S57`). *(Peer-reviewed source)*
