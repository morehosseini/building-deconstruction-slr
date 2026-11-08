# Supplement. LLM evidence check and the SG01 route

Checked reference for the 9 November 2026 manuscript revision. This file is the supplement cited by the new methods and exploratory subsections. It contains no credentials, no raw full texts, no private blind-study mapping and no completed review records. The blind identities are in `AUTHOR_DECISION_LIST.md`, which is an author file and is not part of this supplement.

Software title in the local archive: Gemini-Assisted Scoring of Building Deconstruction Research Evidence, version 0.3.0, package date 8 November 2026, MIT licence. Active seal `a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d`. No public deposit identifier was verified, so none is given here. A journal statement on artificial-intelligence use, data and software waits on the journal choice.

## 1. What the workflow did

The first author screened the records, wrote the gap statements and assigned the scores. The workflow then proposed, for each publication–subgroup pair, a score, a rationale, a limitation and supporting passages. It did not select studies, write the original gap statements, or replace a score.

Page-indexed text was extracted locally with PyMuPDF 1.26.5. Each request received the PDF and that text. One request covered one publication and five subgroup definitions, so a complete pass used five requests per publication.

The rubric is the manuscript’s Table 4.

- Score 0 is a full-text relevance decision. Similar keywords are not enough.
- Score 1 is recognition without a contribution.
- Score 2 is a contribution that is not evaluated.
- Score 3 is an implemented contribution tested, but not against observations from an actual deconstruction project. A real building used only as geometry, and a simulation case, stay at or below 3.
- Score 4 is an implemented contribution tested against recorded observations or data from an actual deconstruction project. The cited data have to evaluate the specific capability.
- If extraction fails, or the decisive evidence is visual, the pair is held. It is not recoded as 0. The unresolved flag is separate.

## 2. Models, partition and settings

| Item | Recorded value |
|---|---|
| Flash, baseline and example-conditioned | `gemini-3.8-flash` |
| Separate pass | `gemini-4-argon` |
| Temperature on the repaired assess calls | 0 |
| Thinking | High |
| Maximum output tokens | 65,536 |
| Requests | Serial. `model_config()` sets `max_concurrent_requests = 1` and `max_retries = 4` |
| YAML ceilings | The YAML file also records retries and concurrency above those forced values. The manuscript reports the repaired execution, not the unused YAML ceilings |
| Dependencies in `requirements.txt` | google-genai 1.47.0, PyMuPDF 1.26.5, PyYAML 6.0.3, openpyxl 3.1.5, jsonschema 4.25.1 |

The 59 records are partitioned by study family: 12 calibration, 12 benchmark and 35 production. There are 42 families. Nine contain more than one record and stay inside one partition. The other 33 contain one record. `METHODS.md` says 34 singletons. The live plan has 33, and 33 is the count used here. No family crosses a split.

Out-of-scope placement: S51 is in calibration, S47 is in the benchmark, and S55 and S57 are in production. The synthesis still excludes all four.

Calibration in this workflow means that examples were placed in the prompt. The five frozen examples are S01/SG07, S01/SG02, S01/SG05, S01/SG01 and S17/SG01. An example from the same family as the publication being scored is omitted. Argon receives the rubric and the source document, without examples and without the other ratings. The baseline Flash pass is the historical comparison. It is not a second blinded human rating.

Earlier inspection of S02 and S03, and a later bounded pilot of S05 and S12, are separate from the 300-pair table. Responses were retained across seals. Those pilot files are not re-interpreted here as a prospective validation.

The prompt asks for a score, a rationale, a limitation, a page and an evidence role. Local checks test the schema, the rubric and the roles required by the proposed score. A quotation passes only when it matches contiguous source text after limited normalisation, its numbers keep their original boundaries, and its page is valid. Passing statuses are exact, normalised contiguous, and a genuine continuation across an adjacent page. Failing statuses are wrong page, uncertain layout, unverified or spliced text, too short, and page out of bounds. A matching quotation is not treated as proof that the passage supports the score. Rejected batches are retained. An original execution is kept distinct from a later offline revalidation under the new seal.

The code, the rubric file and the prompt function are in the local archive named by `CODE_AVAILABILITY.md`. That note also lists the exclusions: publisher PDFs, marked-up manuscripts, raw provider caches, credentials, and `work/review/private_keys/`.

## 3. Benchmark sensitivities

The body table uses all 300 holdout pairs, including the out-of-scope record S47. The two sensitivities below were recomputed from the same export on 9 November 2026. They are descriptive. They are not an independent-pair test, and they are not inputs to Tables 5–7.

### 3.1 Building-eligible holdout, 275 pairs

S47’s 25 pairs are removed. All 19 first-author score-4 reference pairs remain.

| Pass | Exact | Within one | MAE | Unweighted kappa | Score 4 matched / assigned |
|---|---:|---:|---:|---:|---:|
| Baseline Flash | 217/275 (78.91%) | 238/275 | 0.4691 | 0.6014 | 10/20 |
| Example-conditioned Flash | 211/275 (76.73%) | 235/275 | 0.5091 | 0.5717 | 10/19 |
| Argon | 212/275 (77.09%) | 242/275 | 0.4582 | 0.6154 | 18/37 |

### 3.2 Non-zero reference, 100 pairs

Restricted to holdout pairs whose first-author score is above 0. Agreement is lower than on the full 300, where many shared zeros contribute to exact agreement.

| Pass | Exact | Within one | MAE | Unweighted kappa | Score 4 matched / assigned |
|---|---:|---:|---:|---:|---:|
| Baseline Flash | 57/100 (57.00%) | 70/100 | 0.9600 | 0.3993 | 10/16 |
| Example-conditioned Flash | 57/100 (57.00%) | 68/100 | 0.9900 | 0.3997 | 10/15 |
| Argon | 71/100 (71.00%) | 85/100 | 0.5000 | 0.5597 | 18/31 |

Argon still matches 18 of the 19 reference score-4 pairs. Assignments that fell on a zero reference are outside this 100, so the assigned count is 31 rather than 37. Eighteen of those 31 match the reference.

The quotation audit for this benchmark is 1,561 passing quotations out of 1,800, and 239 non-passing. The status split and the S02/SG10 role-only failure are in `METRIC_AND_EVIDENCE_TRACE.md`.

## 4. Worked route: SG01 in Table 5

Subgroup name, from the seal and from Table 4: **Automating disassembly model preparation**.

This route is the Table 5 example. It does not close. The break is part of the result.

### 4.1 What Table 5 currently uses

From `4. RA and RR calc Final.xlsx`, sheet `RR calc`, row SG01, confirmed against the Evidence sheet:

| Input | Value |
|---|---|
| n1, n2, n3, n4 | 7, 4, 25, 2 |
| N, positive assessments | 38 |
| Score 0 among the 55 building-scope records | 17 |
| Earliest date on the RR sheet | 1 July 2002 |
| Cutoff | 30 September 2026 |
| Exposure | 8,857 days / 365.25 = 24.2491 years |
| RA | 38 / 24.2491 = 1.567 |
| Contribution, evaluation, project observations | 31/38 = 81.58%, 27/38 = 71.05%, 2/38 = 5.26% |

The manuscript displays these figures. This revision did not change them. If the denominator were all 55 records, the project-observation figure would be 2/55 = 3.64%. That is a different question and is not the Table 5 percentage.

### 4.2 Where the date comes from, and where the register does not

The temporal sheet attributes the 1 July 2002 date to S46, Schultmann and Rentz (2002). In the 76-statement gap register, S46’s row is G062. Its statement is the need for deconstruction scheduling models to incorporate uncertainty and weak data through stochastic or fuzzy methods. Its primary subgroup is **SG23**, not SG01. The grouping note says this uncertainty gap is distinct from G006.

S46 does have an SG01 row in the scoring workbook. The score is 1. The timing flag is “Baseline or earlier capability; excluded from follow-up”. The basis calls it a new full-text relevance check and a recognition score. A score of 1 is not a primary SG01 gap statement in the register, and it is not a score-4 project observation for this subgroup.

The register rows whose primary subgroup is SG01 are later statements:

| Gap | Study | What the statement concerns |
|---|---|---|
| G015 | S14 | Automating topological enrichment and connection geometry for low-detail models |
| G031 | S29 | Constraint matrices built by hand |
| G039 | S33 | Manual clustering of elements into reusable components |
| G048 | S38 | Automated extraction of BIM data into disassembly models |
| G051 | S40 | Manual arbitration of topological relationships |
| G054 | S41 | Manual population of disassembly-graph data. The note says the quotation cites earlier work and the lineage should be checked |
| G057 | S43 | Manual registration of data for analytical disassembly models |

The Table 5 window therefore cannot be traced from a primary SG01 register statement to S46. Using 2002 as the origin of SG01 mixes a temporal-sheet attribution with a register row that belongs to SG23.

### 4.3 Score 3 and score 4 on the same subgroup

The project-observation numerator for SG01 is 2. Both rows are first-author scores. Neither has a reviewed replacement.

**S01, Akbarnezhad et al., workbook year 2012, score 3.** Timing: later year, eligible by publication year. The workbook describes automated transfer of component information into a worked case based on part of a housing project. Treatment scenarios, prices and future life cycles are assumptions. No site-observed dismantling time, productivity, removal sequence or recovery outcome is used to check the contribution. The basis also says the text does not report an accuracy or effort benchmark, and that original page numbers were not inferred from the deidentified Word copy. A real building used as the setting of an assumed case is score 3 under the rubric. It is not score 4. The 2012 workbook year disagrees with the 2014 issue date of the Automation in Construction article identified in the 4 November assessment. That date was not changed here.

**S17, Gordon et al., 2023, score 4.** A warehouse undergoing demolition and recovery in Geneva. The workbook says beam reconstruction is compared with hand-measured component dimensions from that site. The basis limits the score: geometry and count are what the observations check. The same basis says a score of 4 does not validate a removal sequence, structural safety or recovery outcome.

**S50, Volk et al., 2018, score 4.** Hospital St. Georg, Bad Pyrmont, audited in July 2015 and later deconstructed. The detailed model covers one floor. Inventory masses are compared with on-site weights, including the workbook’s concrete figure of 47,781 kg and gypsum figure of 702 kg. The basis says expected values of 199,815 kg and 7,711 kg are much higher and do not reconcile with those measurements. The score records that an actual-project measurement was used. It does not record that the inventory was accurate, and it does not validate the schedule. S17 and S50 are different projects. Their two assessments are not two replications of one dataset.

**S06, Allam and Nik-Bakht, 2025, score 3 on SG08 rather than on SG01.** Included because the body uses it as the quotation example, and because it shows the same score-3 boundary. The workbook says the framework was tested on two benchmark models authored in Revit. No observed project sequence or measured site duration is supplied. Both models proposed 3 for SG08. The Flash batch was rejected because a page-17 quotation was an ellipsis splice. Argon’s quotations for that pair passed. The queue row has no final score. The shared proposed score did not establish the quotation, and the failed quotation has not changed the first-author score.

### 4.4 Eligibility, timing and the profile

S01, S17 and S50 are inside the 55-publication synthesis. S46 is as well. S46’s SG01 score of 1 is one of the 38 positive assessments and is one of the 31 baseline-or-earlier positives in the whole matrix. It is inside the current-corpus N. It would be baseline, not a follow-up success, if a follow-up numerator were built.

The two score-4 assessments are both flagged “Later year; eligible by publication year”. They are the whole of the 5.26% project-observation component. Reclassifying either one would change that percentage. No reclassification is authorised. Shared families elsewhere in the matrix, including FAM_SCHULTMANN for S45 and S46, mean that several publication rows can describe related project evidence. For SG01, the two score-4 rows are not that kind of pair.

### 4.5 What would have to be true before this route could support a priority

1. A primary SG01 register statement, or an explicit decision that the temporal-sheet date is only an earliest located mention and not the origin of the requirement.
2. A signed treatment of G054’s citation lineage and of the other open grouping notes.
3. A decision on whether N continues to include the baseline statement and the earlier positives.
4. Source review of S17 and S50, with the limitation that S50’s mass comparison does not confirm the schedule and does not, on the workbook’s own figures, confirm the expected inventory.
5. A human decision on any model challenge, including S06/SG08. Until then the profile effect is unchanged: n4 remains 2 and the project-observation percentage remains 2/38.

## 5. Human review, as far as it has gone

The independent packet contains 125 blank ratings. Prior scores are withheld. The generator took one publication from each of five eligible benchmark families and stored the mapping privately. On 9 November 2026 the sheet was unsigned and unlocked, so this supplement does not name the five publications.

The supervisory queue contains 188 items and no signed adjudication. Triggers, as tokens that can overlap on one row, are 119 three-way disagreements, 93 evidence-validation failures, 38 score-4 candidates, 25 scope or eligibility flags, 4 baseline-stage differences and 2 verified-agreement controls. The 119 is not the holdout disagreement count. The holdout count is 94.

The operational snapshot is 99 accepted Flash/Argon batches and 491 outstanding, against a 590-batch gate. Those counts do not measure how many studies were reviewed by a person.

## 6. What this supplement does not establish

A checked excerpt does not establish full-paper relevance, a correct model score, or a completed review. Agreement with the first author is not accuracy. Score 4 is not a claim that the method performed well. The current-corpus percentages are not a follow-up analysis. The local software archive is not a public deposit.
