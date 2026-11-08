# Metric and evidence trace

9 November 2026. Every figure below was recomputed from the named file in this session, except the quotation-status counts, which are taken from the audited JSON and identified as such. The sealed comparison export was not modified.

**Export:** `comparison_9cc23fc8b615.csv` under seal `a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d`

**SHA-256:** `0e8c4168a3874ec79ab071cd6807b2e888d8342de544befb44c7d7b66d180508`

The export has 1,475 rows and 23 columns. Open it as UTF-8 with a byte-order mark. `reviewed_score`, `reviewer` and `decision_reason` are empty on every row.

## Populations

| Set | Count | Rule |
|---|---:|---|
| Evidence-sheet rows | 1,475 | 59 records × 25 subgroups |
| Outside building scope | 100 | S47, S51, S55, S57, all score 0 |
| Building-scope pairs | 1,375 | 55 × 25 |
| Score 0 inside that set | 887 | Excluded from the paper percentage |
| Positive assessments | 488 | 113 + 94 + 249 + 32 |
| Holdout pairs | 300 | `split = holdout`, 12 records, including S47 |
| Building-eligible holdout | 275 | The 300 pairs without S47 |
| Non-zero reference holdout | 100 | Holdout pairs with the first author’s score above 0 |

The manuscript states 503 database records, 150 duplicates, 353 deduplicated records, 214 title/abstract exclusions, 139 sought, 103 retrieved, 36 unavailable and 59 included. That chain was not re-audited against the screening workbook.

## Paper percentages

For each subgroup, N = n1 + n2 + n3 + n4. Score 0 is not in N. No subgroup has N = 0.

- Contribution = (n2 + n3 + n4) / N = 375 / 488 = 76.84%
- Evaluation = (n3 + n4) / N = 281 / 488 = 57.58%
- Project observations = n4 / N = 32 / 488 = 6.56%

These use the summed counts. They are not the mean of the 25 subgroup percentages. All 25 subgroup count rows match `4. RA and RR calc Final.xlsx`, sheet `RR calc`.

The program’s finalisation summary divides by every building-scope score, including 0:

- 375 / 1,375 = 27.27%
- 281 / 1,375 = 20.44%
- 32 / 1,375 = 2.33%

The manuscript reports this second set with its own label. It does not replace Table 7 or Figures 4–6. Neither percentage is a proportion of distinct projects. The 32 score-4 assessments come from seven studies: S17, S24, S45, S46, S49, S50 and S54.

## Timing, which blocks a follow-up rate

Among the 488 positive assessments:

- 389 are “Later year; eligible by publication year”
- 31 are “Baseline or earlier capability; excluded from follow-up”
- 68 are “Later year; cutoff date pending verification”

Every subgroup has at least one baseline-or-earlier positive. SG13, SG19 and SG25 have no later-eligible positive. SG14 has no later-eligible positive, one cutoff-pending positive and two baseline-or-earlier positives. The reported attention and resolution figures are current-corpus profiles.

SG01 in Table 5 remains N = 38, earliest date 1 July 2002, cutoff 30 September 2026, Wg = 8,857 / 365.25 = 24.2491 years, RA = 1.567, contribution 31/38 = 81.58%, evaluation 27/38 = 71.05%, project observations 2/38 = 5.26%. The two score-4 rows are S17 and S50.

## Exploratory agreement

Recomputed from holdout rows. Both scores were integers from 0 to 4 on every pair in these sets. Kappa is unweighted Cohen’s kappa. Pairs inside a publication, and publications inside a family, are dependent. There is no independent-pair interval and no claim of accuracy.

| Set | Pass | Exact | Within one | MAE | Kappa | Score 4 matched / reference | Score 4 assigned |
|---|---|---:|---:|---:|---:|---:|---:|
| 300 | Baseline Flash | 237/300 (79.00%) | 258/300 | 0.4800 | 0.5845 | 10/19 | 20 |
| 300 | Example-conditioned Flash | 230/300 (76.67%) | 254/300 | 0.5233 | 0.5525 | 10/19 | 19 |
| 300 | Argon | 228/300 (76.00%) | 258/300 | 0.5100 | 0.5846 | 18/19 | 37 |
| 275, S47 removed | Baseline Flash | 217/275 (78.91%) | 238/275 | 0.4691 | 0.6014 | 10/19 | 20 |
| 275 | Example-conditioned Flash | 211/275 (76.73%) | 235/275 | 0.5091 | 0.5717 | 10/19 | 19 |
| 275 | Argon | 212/275 (77.09%) | 242/275 | 0.4582 | 0.6154 | 18/19 | 37 |
| 100, reference above 0 | Baseline Flash | 57/100 (57.00%) | 70/100 | 0.9600 | 0.3993 | 10/19 | 16 |
| 100 | Example-conditioned Flash | 57/100 (57.00%) | 68/100 | 0.9900 | 0.3997 | 10/19 | 15 |
| 100 | Argon | 71/100 (71.00%) | 85/100 | 0.5000 | 0.5597 | 18/19 | 31 |

The 19 reference score-4 pairs all have a positive first-author score, so they remain inside the 100-pair set. Argon’s 37 score-4 assignments on the full 300 include assignments on zero-reference pairs, which is why the assigned count falls to 31 in the 100-pair set. The matched count stays 18. Removing S47 does not remove any of the 19 reference pairs.

Adding the five examples did not improve exact agreement on the 300 pairs (237 against 230).

Audit extras, not manuscript findings: three-way exact agreement 206/300 and 190/275. Flash-versus-Argon kappa 0.6804 on 300 pairs (244/300 equal) and 0.6814 on 275. The 94 holdout disagreements split into 24 pairs at the 0-versus-1 boundary, 31 at 0-versus-3, 12 at 2-or-3-versus-4, and 27 other.

## Quotation audit

From `benchmark_recomputation_audit.json`, historical benchmark seal `946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5`. SHA-256 of the audit file: `e4da322bbc014f8890b6ccbb75682b9b0eca7f688c7993029e1a10cad1d23392`.

Of 1,800 quotations, 1,561 passed (15 exact, 1,546 normalised contiguous, 0 cross-page) and 239 did not (174 unverified, 62 uncertain layout, 3 wrong page). Failed quotations affect 88 pairs. S02/SG10 has an evidence-role failure and no failed quotation. Any validation failure: 89 pairs. This audit is the benchmark set. It is not the S05/S12 pilot and it is not S06.

## S06 / SG08

Comparison-export row, production split, building scope yes:

| Field | Value |
|---|---|
| First-author score | 3 |
| Baseline Flash | Empty. Status `missing` |
| Example-conditioned Flash | 3. Status `rejected_evidence` |
| Argon | 3. Status `accepted` |
| Reviewed score | Empty |
| Flags | `flash_batch_rejected`, `flash_validation_failed`, `flash_evidence_unverified` |

The queue has one matching row. Its trigger is `evidence_validation_failure`. Its final score is empty. Its baseline cell is −1 because the baseline score is missing. That value is not a score on the 0–4 rubric.

The supplied PDF has 23 pages. On page 17 the rejected Flash quotation places an ellipsis between “in P6 Professional” and “The second approach involved testing the deconstruction logic”. Both ends are on the page. The intervening sentences, on the warning log, milestones and relationships, mean the quotation is not contiguous. Argon’s SG08 quotations passed the contiguous-text check. No human decision has been recorded. The workbook scores the pair 3 because the tests use authored Revit benchmark assemblies, not recorded deconstruction operations.

## Gate

| Object | State on 9 November 2026 |
|---|---|
| Accepted Flash/Argon batches | 99 = 73 historical holdout + 19 pilot + 7 imported |
| Outstanding | 491 = 47 holdout rescore + 120 calibration + 324 production |
| Required for the gate | 590 |
| Blind sheet | 125 rows, 0 scores, unlocked |
| Queue | 188 rows, 0 final scores |
| Queue tokens | 119 three-way, 93 evidence-validation, 38 score-4 candidate, 25 scope, 4 baseline-stage, 2 agreement-control |

The 119 three-way token is larger than the 94 holdout disagreements because the queue also contains pilot rows and S06. Baseline records, rejected batches, raw responses, retries and provider attempts are different units. None of these counts is a human agreement statistic.

`pipeline.py` writes the review columns empty and does not overwrite a filled review sheet. `verify_independent_review_lock` requires a locked status, a completed-by name, a timestamp, a SHA-256 match, 125 unique pairs, and scores from 0 to 4 with a rationale. That lock is absent. `finalize` divides by all building-scope scores, including 0. Its output was not used as the manuscript percentage.
