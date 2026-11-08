# Input Specification

Provide lawfully accessible local copies of the review inputs in the directory layout below (default relative location `../2026-11-07_Scoring_Evidence`, or pass `--source-dir` where supported):

```text
2026-11-07_Scoring_Evidence/
  02_Scoring_Criteria_and_Evaluation/
    Scoring criteria for assessing.docx
    Sub group Scoring 0-4.xlsx
  03_Full_Text_PDFs/
    [59 original research article PDFs]
  04_Marked_Up_Studies/
    [59 marked-up Word documents used for operator verification]
```

## Authority and Validation Requirements

1. **Scoring Authority (`Scoring criteria for assessing.docx`)**: Supplies the exact verbatim rubric (`Table 4`). `pipeline.py seal` verifies that the extracted DOCX text and all 25 subgroup requirements (`SG01`–`SG25`) match [rubric_reference.json](rubric_reference.json) byte-for-byte.
2. **Reference Workbook (`Sub group Scoring 0-4.xlsx`)**: Contains an `Evidence` worksheet with required columns `Study ID`, `Subgroup`, `Shared research requirement`, `Paper title as supplied`, and `Assessed score` across `S01`–`S59` and `SG01`–`SG25` (`59 × 25 = 1,475` unique pairs; integer scores `0`–`4`).
3. **Original Research PDFs (`03_Full_Text_PDFs/`)**: All 59 PDFs are hashed with SHA-256 during `extract` and re-verified on every `seal`, `assess`, `import-historical`, `export`, and `finalize` invocation. Note that study `S56` (*Karsan et al., 2025*) contains an embedded PDF font lacking a `ToUnicode` CMap (`ASCII - 31` shift in extracted text while vector PDF rendering remains intact); its assessments require multimodal visual inspection and human review verification.

## Data Sharing & Privacy Boundaries

The MIT software supplement includes [rubric_reference.json](rubric_reference.json), executable code, audit/provenance/review-packet scripts, and documentation, while excluding copyrighted full-text PDFs, marked-up Word files, API keys, raw provider caches, and private blind-review mapping keys. Independent human review (`work/review/blind_reviewer_packet/`) and supervisory adjudication (`work/review/adjudication_queue.csv`) remain pending human completion prior to final synthesis release.
