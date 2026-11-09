# Supplementary data dictionary

## study_subgroup_scores.csv

One row is one publication–subgroup assessment made by the first author. There are 59 studies × 25 subgroups = 1,475 unique rows. Filtering `building_scope_in_synthesis = 1` gives 55 studies and 1,375 pairs. Four excluded records, S47, S51, S55 and S57, remain in the inventory with the flag 0.

- `study_id`, `subgroup_id`: source-workbook identifiers; their combination is unique.
- `paper_title_as_supplied`, `year_as_recorded`: source-workbook metadata, not independently verified bibliography.
- `first_author_score`: 0 = no relevant gap recognition or contribution, 1 = recognition only, 2 = contribution proposed without evaluation, 3 = contribution evaluated without project observations, 4 = contribution evaluated using actual project observations. Score 4 does not guarantee the contribution worked or was practice-ready.
- `building_scope_in_synthesis`: 1 for the manuscript synthesis and 0 for the four out-of-scope records.

Among the 1,375 in-scope rows, scores 0–4 occur 887, 113, 94, 249 and 32 times, respectively. The research-resolution denominator N excludes score 0; hence N = 488 in the pooled analysis. Contribution = (94 + 249 + 32)/488, evaluation = (249 + 32)/488, and project observation = 32/488. The 32 are publication–subgroup assessments, not 32 independent projects. Model ratings are not substituted for human scores in this file.

## gap_register_summary.csv

One row per identified gap statement: `gap_id`, `primary_subgroup`, `shared_requirement`, `paper_title_as_supplied`, `gap_statement_summary`, and `study_id` are copied from the first author's 76-row register. Gap summaries are the author-written summaries; source quotations, page-level evidence and private notes are not included. A gap's primary subgroup is not necessarily its only possible relationship. The SG01 reference date used in the manuscript cannot be traced to an SG01-assigned statement in the source register; interpret SG01's attention rate with caution.

The data files document the current-corpus assessment and do not establish that a rated contribution was published after the earliest gap statement. Ratings within a publication and related study families are dependent. Source articles, complete screening records and page-level justifications are held by the authors.

## title_abstract_screening.csv

One row per title–abstract record. The three concept columns record the first author’s screening assessments as Yes, No or Unclear. `decision` is Retain or Exclude, `main_exclusion_reason` is the stated primary criterion where applicable, and `retained_with_uncertainty` records uncertain inclusions. Database sources and DOI are as recorded. The file contains 353 rows: 139 retained and 214 excluded. It does not contain the abstracts, the subsequent full-text decisions or the 36 unavailable full texts.
