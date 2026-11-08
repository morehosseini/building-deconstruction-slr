#!/usr/bin/env python3
"""Generate isolated Independent Blind Reviewer Packet and Evidence-Grounded Adjudication Queue.

Enforces strict separation:
  1. work/review/blind_reviewer_packet/
     - pdfs/BLIND_STUDY_01.pdf .. BLIND_STUDY_05.pdf (byte-verified copies of original PDFs)
     - BLIND_REVIEWER_INSTRUCTIONS.md (verbatim Dulshan rubric + exact 25 subgroup definitions, status=PENDING)
     - blind_reviewer_scoring_sheet.csv (125 blank rows; zero study IDs, mapping keys, or prior scores)
  2. work/review/private_keys/
     - private_mapping.json (kept strictly outside the reviewer packet and public supplement)
     - independent_review_status.json (records review as pending and unlocked until human completion)
  3. work/review/adjudication_queue.csv
     - Built from the repaired sealed export; includes 100% of evidence/validation failures,
       all 94 three-way disagreements (plus baseline differences), all 38 Score-4 candidates (including S54/SG21
       carrying human_score_4), all scope-flagged pairs (S47), and verified agreement controls.
     - Grounds adjudication notes and proposals in inspected PDF and workbook source evidence rather than
       defaulting to a preferred rater.
"""
import argparse
import csv
import hashlib
import json
import re
import secrets
import shutil
from pathlib import Path

DEFAULT_VERSION = "a8c4ad874ce9e8546cb9b26fca88c1e1605ef4b83581367e61f4a9232c7e889d"
PASSING_STATUSES = {"exact", "normalized_contiguous", "cross_page_contiguous"}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_review_packet_not_started(blind_dir: Path, private_dir: Path):
    """Never overwrite a locked or partially completed human review."""
    status_path = private_dir / 'independent_review_status.json'
    if status_path.exists() and json.loads(status_path.read_text(encoding='utf-8')).get('locked'):
        raise ValueError('Independent review is locked; refusing to replace its packet')
    sheet = blind_dir / 'blind_reviewer_scoring_sheet.csv'
    if sheet.exists():
        fields = ('reviewed_score', 'cited_pdf_page', 'verbatim_evidence_quote',
                  'justification_rationale', 'visual_evidence_needs_review', 'notes_or_uncertainty')
        with sheet.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or any(k not in reader.fieldnames for k in fields):
                raise ValueError('Existing blind review sheet has unexpected columns; refusing to replace it')
            if any(any((r.get(k) or '').strip() for k in fields) for r in reader):
                raise ValueError('Independent review has started; refusing to replace its packet')


def ensure_adjudication_not_started(queue: Path):
    """Do not discard human adjudication when regenerating a review queue."""
    if queue.exists():
        fields = ('final_human_adjudicated_score', 'human_adjudicator_name',
                  'adjudication_decision_rationale', 'sign_off_date')
        with queue.open(encoding='utf-8-sig', newline='') as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or any(k not in reader.fieldnames for k in fields):
                raise ValueError('Existing adjudication queue has unexpected columns; refusing to replace it')
            if any(any((r.get(k) or '').strip() for k in fields) for r in reader):
                raise ValueError('Human adjudication has started; refusing to replace the queue')


def clean_snippet(text: str, limit: int = 220) -> str:
    if not text:
        return ""
    s = " ".join(str(text).split())
    return s if len(s) <= limit else s[: limit - 3] + "..."


def classify_disagreement(h: int, f_score: int, a_score: int) -> str:
    vals = {h, f_score, a_score}
    if len(vals) == 1:
        return "three_way_agreement"
    if vals.issubset({0, 1}):
        return "0_vs_1_gap_recognition"
    if 4 in vals and bool(vals & {2, 3}):
        return "2_or_3_vs_4_project_observations"
    if {0, 3}.issubset(vals):
        return "0_vs_3_tested_contribution_scope"
    return "other_intermediate_boundary"


# Inspected source-evidence notes for specific landmark Score-4 and boundary cases
LANDMARK_EVIDENCE_NOTES = {
    ("S54", "SG21"): (
        "NEEDS_HUMAN_DETERMINATION (4 vs 1/0)",
        "PDF p. 21 ([YB11]-[YB12]) & pp. 31, 40 document ~190 h field observation of a 4-storey, 68-module Hong Kong "
        "transitional housing building where irreversible MEP tie-ins were forcefully removed/disposed alongside "
        "reversible bolted T-section/tie-plate joint release. Dulshan workbook scores 4 as empirical documentation of "
        "mixed destructive/non-destructive operations; Baseline/Flash (0) and Argon (1) require a planning method "
        "evaluating alternative dismantling modes. Human adjudicator must rule whether empirical field documentation "
        "of forced vs reversible separation satisfies SG21."
    ),
    ("S46", "SG10"): (
        "2 (or 1; reject Argon 4)",
        "PDF p. 9 ('Solution procedure') explicitly states: 'Since the purpose of this work is not the development or "
        "improvement of an efficient algorithm for resource constrained project scheduling problems, we used a slightly "
        "modified version of the algorithm proposed by Sprecher and limited the computation time for certain problems... "
        "in 25% of the cases considered only sub-optimal solutions could be found.' Argon's Score 4 over-credits the "
        "domestic-building case comparison (408 h vs 221 h, p. 9) to computational scalability and failed layout verification "
        "(scanned fi/fl ligature artefact on p. 9)."
    ),
    ("S45", "SG10"): (
        "3 (or 1; reject Argon 4)",
        "PDF pp. 13-14, 17-19 formulate and solve the multi-mode RCPSP for a three-storey domestic masonry building "
        "(Mulhouse dwelling-house), noting NP-hardness and computational time bounds without validating computational "
        "scalability against field measurements. Domestic building field data (408 h baseline, Rentz et al., 1998) do "
        "not test algorithmic scalability at Score 4."
    ),
    ("S45", "SG03"): (
        "4",
        "PDF pp. 4-9, 15, 17 (Tables 1-3, Figs. 1, 5, 9) compile and apply empirical pre-demolition building audit bills "
        "of materials, pollutant matrices, and measured dismantling durations/costs from four residential/hotel/industrial/school "
        "pilot buildings (Dobel, Mulhouse, Strasbourg, Rottweil; Rentz et al., 1998a). Baseline (2) and Calibrated Flash (2) "
        "missed that the empirical data framework was directly evaluated across recorded dismantling projects."
    ),
    ("S54", "SG03"): (
        "4",
        "PDF pp. 13-25 ([YB02], [YB05], [YB11]-[YB24]) report primary empirical dismantling, logistics, storage, and "
        "reassembly observations (~190 observation hours + 4 interviews + demolition/logistics plans) for a 68-unit "
        "four-storey modular building in Hong Kong. Calibrated Flash (4), Argon (4), and Dulshan (4) converge; Baseline "
        "Flash (2) under-credited empirical evaluation."
    ),
    ("S45", "SG21"): (
        "3",
        "PDF pp. 8, 11, 16-17 model alternative dismantling modes (manual pneumatic hammer vs grabbing bucket vs hydraulic "
        "excavator; Scenarios 1-3) in an MRCPSP for a domestic masonry building. Only the conventional baseline (408 h) "
        "was observed in practice; Scenarios 1-3 (221 h, 165 h, 185 h) are computational schedule projections (Score 3, not 4)."
    ),
    ("S46", "SG21"): (
        "3",
        "PDF pp. 7, 9-10 model manual (Scenario 1), partly automated machine (Scenario 2), and selective separation "
        "(Scenario 3) modes for a three-storey domestic building. Scenarios 1-3 are simulated optimisation runs compared "
        "retrospectively against the single 408 h practical baseline (Score 3, not 4)."
    ),
    ("S46", "SG04"): (
        "3",
        "PDF pp. 8-10 formulate cost and makespan objectives across Scenarios 1-3 for a domestic building; multi-scenario "
        "cost/recycling trade-offs are evaluated computationally against a single historical baseline rather than observed "
        "multi-scenario site execution (Score 3)."
    ),
    ("S45", "SG08"): (
        "3",
        "PDF pp. 6, 10, 16 represent a 27/29-activity topological dismantling network and residential bill of materials; "
        "scenario schedule network extensions (Scenario 3, Fig. 8) are evaluated computationally (Score 3)."
    ),
    ("S46", "SG08"): (
        "3",
        "PDF pp. 6, 10 model a 28-activity topological dismantling network for a three-storey residential building; "
        "combined/extended scenario schedules are evaluated computationally (Score 3)."
    ),
    ("S45", "SG06"): (
        "NEEDS_HUMAN_DETERMINATION (0 vs 3/4)",
        "PDF pp. 6, 8, 10, 15-17 model whole-building dismantling of a three-storey domestic masonry building (plus "
        "summary comparisons across four buildings on p. 15). Models (4/4/4) treat whole-building audit+MRCPSP as "
        "addressing SG06; Dulshan (0) restricts SG06 to explicit scaling extensions beyond standard single-building networks."
    ),
    ("S46", "SG06"): (
        "NEEDS_HUMAN_DETERMINATION (0 vs 3/4)",
        "PDF pp. 6, 9-10 model a 28-activity dismantling network for a three-storey residential building. Models (4/4/4) "
        "score whole-building scheduling; Dulshan (0) requires explicit methodological extension to complex/large-scale systems."
    ),
    ("S50", "SG03"): (
        "0 (or 1; reject Flash/Argon 4)",
        "PDF pp. 8-15 (Volk et al., 2018) test automated RGB-D building inventory reconstruction against manual room "
        "audits (scored 4 under SG01), whereas dismantling unit times/costs/rates in the downstream project planner rely "
        "on external database assumptions rather than an empirical planning-data contribution for SG03."
    ),
    ("S50", "SG06"): (
        "1",
        "PDF pp. 14-17 explicitly note sensor range, occlusion, and multi-room scaling limitations when extending RGB-D "
        "capture to complex whole buildings without validating a whole-building solution (Score 1)."
    ),
    ("S50", "SG08"): (
        "3",
        "PDF pp. 6-13 implement component precedence and inventory completeness rules tested on simulated deconstruction "
        "schedules rather than observed physical dismantling sequences (Score 3)."
    ),
    ("S50", "SG24"): (
        "3",
        "PDF pp. 7-13 compute component mass/material inventory recovery outputs in software prototypes; physical recovery "
        "yields during actual building demolition were not measured on site (Score 3)."
    ),
    ("S54", "SG06"): (
        "1",
        "PDF pp. 40-41 explicitly identify as a limitation and future research gap that findings come from one four-storey "
        "temporary demountable modular building and require future extension to high-rise and non-DfD complex buildings (Score 1)."
    ),
    ("S54", "SG09"): (
        "1",
        "PDF pp. 22-26 mention temporary props and post-removal appraisal of 7/68 modules, while noting structural stability "
        "considerations during removal without formulating or testing a structural stability verification method (Score 1)."
    ),
    ("S54", "SG20"): (
        "2",
        "PDF pp. 34-39 propose early circular procurement and stakeholder coordination recommendations from case lessons "
        "without evaluating an implemented early-decision tool on a project (Score 2)."
    ),
}


def build_evidence_audit_and_proposal(sid, sg, r, dul_row):
    h = int(r["dulshan"]) if r.get("dulshan") and r["dulshan"] != "" else -1
    b = int(r["baseline"]) if r.get("baseline") and r["baseline"] != "" else -1
    f = int(r["flash"]) if r.get("flash") and r["flash"] != "" else -1
    a = int(r["argon"]) if r.get("argon") and r["argon"] != "" else -1
    scope = r["building_scope"]

    verified_summaries = []
    failed_summaries = []
    for st in ("baseline", "flash", "argon"):
        evs = json.loads(r.get(f"{st}_evidence") or "[]")
        for e in evs:
            mstat = e.get("match_status", "")
            snippet = f"{st}[p.{e.get('page')},{e.get('role')},{mstat}]: {clean_snippet(e.get('quote', ''), 95)}"
            if mstat in PASSING_STATUSES:
                verified_summaries.append(snippet)
            else:
                failed_summaries.append(snippet)

    dul_basis = clean_snippet(dul_row.get("Evidence basis, subgroup linkage and missing information") or "", 240)

    if scope == "no":
        return (
            "OUT_OF_SCOPE_VERIFY (0 for eligible synthesis)",
            f"Study {sid} is confirmed outside building scope (generic mechanical product/part fuzzy Petri net disassembly, "
            f"PDF pp. 1-5) and excluded from eligible synthesis denominators (N=55). Dulshan recorded {h}; models scored "
            f"B={b}, F={f}, A={a}. Failed quote checks: {len(failed_summaries)}.",
            " | ".join(verified_summaries[:3]),
            " | ".join(failed_summaries[:3]),
            dul_basis,
        )

    if (sid, sg) in LANDMARK_EVIDENCE_NOTES:
        prop, note = LANDMARK_EVIDENCE_NOTES[(sid, sg)]
        if failed_summaries:
            note += f" [Note: {len(failed_summaries)} model quote(s) failed strict contiguous verification and require source page check.]"
        return prop, note, " | ".join(verified_summaries[:3]), " | ".join(failed_summaries[:3]), dul_basis

    vals = {h, f, a}
    if len(vals) == 1:
        if failed_summaries:
            prop = f"VERIFY_SOURCE_QUOTE ({h})"
            note = (
                f"Dulshan, Calibrated Flash, and Blind Argon agree on score {h} (Baseline={b}), but {len(failed_summaries)} "
                f"supporting quotation(s) failed strict contiguous text verification ({', '.join(x.split(':')[0] for x in failed_summaries)}). "
                f"Confirm contiguous wording directly on cited PDF page before locking {h}."
            )
        else:
            prop = str(h)
            note = f"Three-way consensus (H={h}, F={f}, A={a}; Baseline={b}) with contiguous source-verified PDF quotations."
        return prop, note, " | ".join(verified_summaries[:3]), " | ".join(failed_summaries[:3]), dul_basis

    f_acc = (r.get("flash_status") == "accepted")
    a_acc = (r.get("argon_status") == "accepted")
    candidates_sorted = sorted(vals)
    prop = f"NEEDS_HUMAN_DETERMINATION ({'/'.join(str(x) for x in candidates_sorted)})"
    note = (
        f"Scores diverge (Dulshan={h}, Baseline={b}, Flash={f} [{r.get('flash_status')}], Argon={a} [{r.get('argon_status')}]). "
        f"Compare Dulshan workbook note against verified PDF quotations (Flash accepted={f_acc}, Argon accepted={a_acc}, "
        f"failed quotes={len(failed_summaries)}) under exact subgroup requirement '{dul_row.get('Shared research requirement')}'."
    )
    return prop, note, " | ".join(verified_summaries[:3]), " | ".join(failed_summaries[:3]), dul_basis


def load_or_create_private_mapping(private_key_path: Path, studies: dict, count: int = 5) -> dict:
    """Load existing private blind key if present, or sample fresh eligible holdout studies from OS entropy."""
    if private_key_path.exists():
        existing = json.loads(private_key_path.read_text(encoding="utf-8"))
        raw_map = existing.get("mapping", {})
        return {blind_id: (rec["study_id"] if isinstance(rec, dict) else str(rec)) for blind_id, rec in sorted(raw_map.items())}

    eligible_holdout = [
        s for s in studies.values()
        if s.get("split") == "holdout" and s.get("building_scope") == "yes"
    ]
    by_family = {}
    for s in sorted(eligible_holdout, key=lambda x: x["study_id"]):
        by_family.setdefault(s["family_id"], []).append(s["study_id"])
    rng = secrets.SystemRandom()
    families = list(by_family.keys())
    rng.shuffle(families)
    chosen = [rng.choice(by_family[fam]) for fam in families[:count]]
    rng.shuffle(chosen)
    return {f"BLIND_STUDY_{i:02d}": sid for i, sid in enumerate(chosen, start=1)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=Path(__file__).resolve().parent / "work")
    parser.add_argument("--source-dir", type=Path, default=Path(__file__).resolve().parent.parent / "2026-11-07_Scoring_Evidence")
    parser.add_argument("--version", default=DEFAULT_VERSION)
    parser.add_argument("--private-key-file", type=Path, default=None, help="Optional path to private mapping key JSON")
    args = parser.parse_args()

    work = args.work_dir.expanduser().resolve()
    source = args.source_dir.expanduser().resolve()
    version = args.version

    exports_dir = work / "versions" / version / "exports"
    csv_files = sorted(exports_dir.glob("comparison_*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No export CSV found in {exports_dir}")
    comparison_csv = csv_files[-1]

    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    docs = json.loads((work / "documents.json").read_text(encoding="utf-8"))
    authority = json.loads((work / "authority.json").read_text(encoding="utf-8"))
    subgroups = authority["subgroups"]
    studies = {s["study_id"]: s for s in plan["studies"]}
    dul_index = {(r["Study ID"], r["Subgroup"]): r for r in authority["dulshan"]}

    with comparison_csv.open(encoding="utf-8-sig", newline="") as f:
        all_rows = list(csv.DictReader(f))
    holdout_rows = [r for r in all_rows if r["split"] == "holdout"]
    assert len(holdout_rows) == 300, f"Expected 300 holdout rows, found {len(holdout_rows)}"

    review_dir = work / "review"
    blind_dir = review_dir / "blind_reviewer_packet"
    blind_pdfs_dir = blind_dir / "pdfs"
    private_dir = review_dir / "private_keys"
    private_dir.mkdir(parents=True, exist_ok=True)
    private_key_path = (args.private_key_file.expanduser().resolve() if args.private_key_file
                        else (private_dir / "private_mapping.json"))

    ensure_review_packet_not_started(blind_dir, private_dir)
    ensure_adjudication_not_started(review_dir / 'adjudication_queue.csv')
    blind_pdfs_dir.mkdir(parents=True, exist_ok=True)

    # 1. Self-contained Independent Blind Reviewer Packet (mapping stored strictly in private_keys/)
    selected_map = load_or_create_private_mapping(private_key_path, studies, count=5)

    mapping_records = {}
    blind_sheet_rows = []
    author_tokens = set()
    for blind_id, sid in sorted(selected_map.items()):
        st = studies[sid]
        doc = docs[st["pdf"]]
        src_pdf = source / doc["path"]
        dst_pdf = blind_pdfs_dir / f"{blind_id}.pdf"
        shutil.copy2(src_pdf, dst_pdf)
        copied_sha = file_hash(dst_pdf)
        assert copied_sha == doc["sha256"], f"SHA-256 mismatch copying {src_pdf}"
        lead_part = Path(doc["path"]).stem.split(" - ")[0]
        for word in re.findall(r"[A-Za-z]{4,}", lead_part):
            if word.lower() not in {"and", "the", "for", "with"}:
                author_tokens.add(word)
        mapping_records[blind_id] = {
            "study_id": sid,
            "family_id": st["family_id"],
            "original_pdf_relpath": doc["path"],
            "blind_pdf_relpath": f"pdfs/{blind_id}.pdf",
            "pdf_sha256": copied_sha,
        }
        for sg_id in sorted(subgroups):
            blind_sheet_rows.append({
                "blind_study_id": blind_id,
                "blind_pdf_path": f"pdfs/{blind_id}.pdf",
                "subgroup_id": sg_id,
                "shared_research_requirement": subgroups[sg_id],
                "reviewed_score": "",
                "cited_pdf_page": "",
                "verbatim_evidence_quote": "",
                "justification_rationale": "",
                "visual_evidence_needs_review": "",
                "notes_or_uncertainty": "",
            })

    blind_sheet_path = blind_dir / "blind_reviewer_scoring_sheet.csv"
    with blind_sheet_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(blind_sheet_rows[0].keys()))
        writer.writeheader()
        writer.writerows(blind_sheet_rows)

    sg_table_lines = [
        "| Subgroup ID | Exact Shared Research Requirement |",
        "| :--- | :--- |",
    ]
    for sg_id in sorted(subgroups):
        sg_table_lines.append(f"| `{sg_id}` | {subgroups[sg_id]} |")

    instructions_md = (
        "# Independent Blind Human Review Packet — Building Deconstruction SLR\n\n"
        "- **Review Status**: `PENDING INDEPENDENT HUMAN COMPLETION (UNLOCKED)`\n"
        "- **Blinding & Locking Protocol**: Complete this packet using **only** the five PDFs in `pdfs/` "
        "(`BLIND_STUDY_01.pdf` to `BLIND_STUDY_05.pdf`), the verbatim rubric below, and the exact 25 subgroup "
        "definitions below. Do **not** consult prior human scores, model outputs, mapping keys, or the adjudication "
        "queue. Once all 125 rows in `blind_reviewer_scoring_sheet.csv` are completed, compute and record the "
        "SHA-256 hash (`shasum -a 256 blind_reviewer_scoring_sheet.csv`) and sign/date the lock record **before** "
        "any comparison is performed.\n\n"
        "---\n\n"
        "## 1. Author's Exact Scoring Rubric (Verbatim)\n\n"
        "```text\n"
        f"{authority['rubric_verbatim']}\n"
        "```\n\n"
        "---\n\n"
        "## 2. Exact 25 Subgroup Definitions (Verbatim)\n\n"
        + "\n".join(sg_table_lines)
        + "\n\n---\n\n"
        "## 3. Completion & Locking Steps\n\n"
        "1. Open each PDF in `pdfs/BLIND_STUDY_01.pdf` through `pdfs/BLIND_STUDY_05.pdf`.\n"
        "2. For each of the 25 subgroups (`SG01`–`SG25`), assign an integer score `0`, `1`, `2`, `3`, or `4` "
        "(or `-1` if decisive evidence is visual/unextractable and prevents scoring) strictly according to the "
        "verbatim rubric in Section 1.\n"
        "3. For every non-zero score (`1`–`4`), record the 1-based PDF page index in `cited_pdf_page`, a verbatim "
        "contiguous quotation from that page in `verbatim_evidence_quote`, and a concise justification in "
        "`justification_rationale`. For score `0`, confirm full-document coverage in `justification_rationale`.\n"
        "4. Save `blind_reviewer_scoring_sheet.csv` and lock its SHA-256 digest with the supervisory team prior to "
        "unblinding.\n"
    )
    (blind_dir / "BLIND_REVIEWER_INSTRUCTIONS.md").write_text(instructions_md, encoding="utf-8")

    # Verify zero study ID or author-surname leakage inside text files of blind_reviewer_packet/
    forbidden_study_ids = set(studies.keys())
    for text_file in (blind_dir / "BLIND_REVIEWER_INSTRUCTIONS.md", blind_sheet_path):
        content = text_file.read_text(encoding="utf-8")
        for sid_tok in forbidden_study_ids:
            assert re.search(rf"\b{re.escape(sid_tok)}\b", content) is None, f"Blinding violation: {sid_tok} in {text_file.name}"
        for auth_tok in author_tokens:
            assert re.search(rf"\b{re.escape(auth_tok)}\b", content) is None, f"Blinding violation: {auth_tok} in {text_file.name}"

    # Save private mapping key and pending review status strictly outside blind_reviewer_packet/
    private_key_path.write_text(
        json.dumps({"sealed_version": version, "mapping": mapping_records}, indent=2) + "\n",
        encoding="utf-8",
    )
    (private_dir / "independent_review_status.json").write_text(
        json.dumps({
            "sealed_version": version,
            "packet_directory": "work/review/blind_reviewer_packet",
            "total_pairs": 125,
            "status": "pending_human_completion",
            "locked": False,
            "completed_by": None,
            "locked_timestamp": None,
            "locked_scoring_sheet_sha256": None,
            "comparison_with_prior_scores_permitted": False,
        }, indent=2) + "\n",
        encoding="utf-8",
    )

    # 2. Comprehensive Evidence-Grounded Adjudication Queue
    control_pairs = {("S03", "SG01"), ("S03", "SG04"), ("S14", "SG01"), ("S32", "SG01"), ("S50", "SG01")}
    adjudication_rows = []
    expected_ev_fail_pairs = set()
    included_pairs = set()

    evaluated_prod_rows = [
        r for r in all_rows
        if r["split"] == "production" and (
            (r.get("flash") and r["flash"] != "" and r["flash"] != "-1")
            or (r.get("argon") and r["argon"] != "" and r["argon"] != "-1")
            or any(
                fl.endswith("_evidence_unverified")
                or fl.endswith("_validation_failed")
                or fl.endswith("_wrong_page")
                or fl.endswith("_uncertain_layout")
                for fl in r.get("review_flags", "").split("|")
                if fl
            )
        )
    ]
    queue_candidates = holdout_rows + evaluated_prod_rows

    for r in queue_candidates:
        sid, sg = r["study_id"], r["subgroup"]
        h = int(r["dulshan"])
        b = int(r["baseline"]) if r.get("baseline") and r["baseline"] != "" else -1
        f_score = int(r["flash"]) if r.get("flash") and r["flash"] != "" else -1
        a_score = int(r["argon"]) if r.get("argon") and r["argon"] != "" else -1
        flags = [fl for fl in r.get("review_flags", "").split("|") if fl]

        has_ev_failure = any(
            fl.endswith("_evidence_unverified") or fl.endswith("_validation_failed")
            or fl.endswith("_wrong_page") or fl.endswith("_uncertain_layout")
            for fl in flags
        )
        if has_ev_failure:
            expected_ev_fail_pairs.add((sid, sg))

        is_three_way_disagreement = len({h, f_score, a_score} - {-1}) > 1
        is_baseline_diff = b != -1 and len({h, b, f_score, a_score} - {-1}) > 1 and not is_three_way_disagreement
        is_score_4_candidate = 4 in (h, b, f_score, a_score)
        is_scope_issue = r["building_scope"] != "yes"
        is_unresolved = any(fl.endswith("_unresolved_or_visual") for fl in flags)
        is_control = (sid, sg) in control_pairs

        if (
            has_ev_failure
            or is_three_way_disagreement
            or is_baseline_diff
            or is_score_4_candidate
            or is_scope_issue
            or is_unresolved
            or is_control
        ):
            included_pairs.add((sid, sg))
            triggers = []
            if has_ev_failure:
                triggers.append("evidence_validation_failure")
            if is_three_way_disagreement:
                triggers.append("three_way_disagreement")
            if is_baseline_diff:
                triggers.append("baseline_stage_difference")
            if is_score_4_candidate:
                triggers.append("score_4_candidate")
            if is_scope_issue:
                triggers.append("scope_or_eligibility")
            if is_unresolved:
                triggers.append("unresolved_or_visual")
            if is_control and not triggers:
                triggers.append("verified_agreement_control")

            dul_row = dul_index[(sid, sg)]
            prop, note, ver_q, fail_q, dul_basis = build_evidence_audit_and_proposal(sid, sg, r, dul_row)

            adjudication_rows.append({
                "sealed_version": version,
                "study_id": sid,
                "subgroup": sg,
                "shared_research_requirement": subgroups[sg],
                "split": r["split"],
                "building_scope": r["building_scope"],
                "queue_triggers": "|".join(triggers),
                "disagreement_taxonomy": classify_disagreement(h, f_score, a_score),
                "dulshan_score": h,
                "baseline_flash_score": b,
                "baseline_status": r.get("baseline_status", ""),
                "calibrated_flash_score": f_score,
                "calibrated_flash_status": r.get("flash_status", ""),
                "blind_argon_score": a_score,
                "blind_argon_status": r.get("argon_status", ""),
                "review_flags": r.get("review_flags", ""),
                "dulshan_workbook_basis": dul_basis,
                "verified_contiguous_model_quotes": ver_q,
                "failed_or_uncertain_model_quotes": fail_q,
                "evidence_based_proposal": prop,
                "evidence_audit_notes": note,
                "final_human_adjudicated_score": "",
                "human_adjudicator_name": "",
                "adjudication_decision_rationale": "",
                "sign_off_date": "",
            })

    missing_ev = expected_ev_fail_pairs - included_pairs
    assert not missing_ev, f"Missing evidence-failure pairs from queue: {missing_ev}"
    s54_sg21 = next((x for x in adjudication_rows if x["study_id"] == "S54" and x["subgroup"] == "SG21"), None)
    assert s54_sg21 is not None, "S54/SG21 missing from adjudication queue"
    assert "human_score_4" in s54_sg21["review_flags"].split("|"), "S54/SG21 missing human_score_4 flag"

    adj_csv_path = review_dir / "adjudication_queue.csv"
    with adj_csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(adjudication_rows[0].keys()))
        writer.writeheader()
        writer.writerows(adjudication_rows)

    print(f"Blind reviewer packet created in: {blind_dir} (5 PDFs + instructions + {len(blind_sheet_rows)} blank rows)")
    print(f"Private key & pending status saved in: {private_dir}")
    print(f"Adjudication queue saved to: {adj_csv_path} ({len(adjudication_rows)} rows; "
          f"evidence-failure pairs covered: {len(expected_ev_fail_pairs)}/{len(expected_ev_fail_pairs)}, missing=0)")


if __name__ == "__main__":
    main()
