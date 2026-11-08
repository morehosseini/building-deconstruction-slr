#!/usr/bin/env python3
"""Reconstruct complete cryptographic provenance across historical seals, retries, and raw cache.

Links every retained batch, rejected attempt, and provider retry to its:
  - original request cache key (ck),
  - original execution seal,
  - prompt_hash and model_settings configuration (checked against target sealed bundle),
  - source PDF path and SHA-256,
  - raw provider response JSON path, SHA-256, response_id, create_time, finish_reason,
  - verified token usage using usage_metadata.thoughts_token_count and cached_content_token_count.
"""
import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path

import pipeline as p

DEFAULT_HIST_VERSION = "946a8543adc9b28c4195d4544727636b89f108966029a57c8b079ea5d2eb9fe5"
HISTORICAL_REQUEST_ORIGIN_OVERRIDES = {
    # baseline/S54_4 reconstructed request-cache key originating under seal 665aa76e...
    "fdc71772c4a1d2b0792f3ce1365bbf488ca1391ad5550ba17ea173c385268520": "665aa76ed68e8c69c9c58616bd7f119628ec7438ec02c0a8d2681852a6eb3a8a",
}


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def safe_relpath(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        try:
            return path.relative_to(root).as_posix()
        except ValueError:
            return path.as_posix()


def extract_usage(meta: dict) -> dict:
    meta = meta or {}
    prompt_tok = int(meta.get("prompt_token_count") or 0)
    cached_tok = int(meta.get("cached_content_token_count") or 0)
    uncached_tok = max(0, prompt_tok - cached_tok)
    cand_tok = int(meta.get("candidates_token_count") or 0)
    thought_tok = int(meta.get("thoughts_token_count") or 0)
    total_tok = int(meta.get("total_token_count") or (prompt_tok + cand_tok + thought_tok))
    return {
        "prompt_tokens": prompt_tok,
        "cached_prompt_tokens": cached_tok,
        "uncached_prompt_tokens": uncached_tok,
        "candidates_tokens": cand_tok,
        "thoughts_tokens": thought_tok,
        "output_plus_thoughts_tokens": cand_tok + thought_tok,
        "total_tokens": total_tok,
    }


def strip_evidence_keys(resp_obj) -> str:
    if not isinstance(resp_obj, dict):
        return None
    r = json.loads(json.dumps(resp_obj))
    for a in r.get("assessments", []):
        for ev in a.get("evidence", []):
            for k in ("match_status", "matched_pages", "matched_span", "char_spans"):
                ev.pop(k, None)
    return json.dumps(r, sort_keys=True, ensure_ascii=False)


def parse_raw_response(rf: Path, root: Path) -> dict:
    data = json.loads(rf.read_text(encoding="utf-8"))
    stem = rf.stem
    ck = stem.split("_", 1)[0]
    meta = data.get("usage_metadata") or {}
    usage = extract_usage(meta)
    cands = data.get("candidates") or []
    cand0 = cands[0] if cands else {}
    finish = str(cand0.get("finish_reason") or "UNKNOWN")
    parsed_key = None
    if cand0:
        parts = (cand0.get("content") or {}).get("parts") or []
        for pt in reversed(parts):
            txt = pt.get("text")
            if txt and not pt.get("thought"):
                try:
                    obj = json.loads(txt.strip())
                    parsed_key = json.dumps(obj, sort_keys=True, ensure_ascii=False)
                    break
                except Exception:
                    pass
    return {
        "request_cache_key": ck,
        "raw_cache_path": safe_relpath(rf, root),
        "raw_cache_sha256": file_hash(rf),
        "response_id": data.get("response_id") or "UNAVAILABLE",
        "response_timestamp": data.get("create_time") or "UNAVAILABLE",
        "model_version": data.get("model_version") or "UNKNOWN",
        "finish_reason": finish,
        "parsed_json_canonical": parsed_key,
        "token_usage": usage,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", type=Path, default=Path(__file__).resolve().parent / "work")
    parser.add_argument("--historical-version", default=DEFAULT_HIST_VERSION)
    parser.add_argument("--target-version", default=None, help="New sealed version for prompt/config comparison")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    work = args.work_dir.expanduser().resolve()
    root = work.parent if (work.parent / "pipeline.py").exists() else Path(__file__).resolve().parent
    hist_version = args.historical_version
    out_path = (args.output or (work / "provenance_manifest.json")).expanduser().resolve()

    plan = json.loads((work / "plan.json").read_text(encoding="utf-8"))
    docs = json.loads((work / "documents.json").read_text(encoding="utf-8"))
    studies = {s["study_id"]: s for s in plan["studies"]}

    target_version = args.target_version
    target_bundle = None
    if target_version:
        target_bundle = json.loads((work / "versions" / target_version / "bundle.json").read_text(encoding="utf-8"))
    else:
        target_bundle = json.loads((work / "versions" / hist_version / "bundle.json").read_text(encoding="utf-8"))
    sg_ids = sorted(target_bundle["authority"]["subgroups"])

    # 1. Index top-level cache metadata (ck -> label, model, variant, temperature)
    cache_meta_by_ck = {}
    for cf in sorted((work / "cache").glob("*.json")):
        try:
            cdata = json.loads(cf.read_text(encoding="utf-8"))
            cache_meta_by_ck[cf.stem] = {
                "label": cdata.get("label", ""),
                "model": cdata.get("model", ""),
                "variant": cdata.get("variant"),
                "temperature": cdata.get("temperature"),
            }
        except Exception:
            pass

    # 2. Index all 212 raw provider responses across all CKs (including retries & non-STOP)
    raw_by_ck = defaultdict(list)
    raw_by_parsed = defaultdict(list)
    all_raw_entries = []
    raw_dir = work / "cache" / "raw"
    for rf in sorted(raw_dir.glob("*.json")):
        entry = parse_raw_response(rf, root)
        all_raw_entries.append(entry)
        raw_by_ck[entry["request_cache_key"]].append(entry)
        if entry["parsed_json_canonical"] is not None:
            raw_by_parsed[entry["parsed_json_canonical"]].append(entry)

    for ck in raw_by_ck:
        raw_by_ck[ck].sort(key=lambda x: (x["response_timestamp"], x["raw_cache_path"]))
    for pk in raw_by_parsed:
        raw_by_parsed[pk].sort(key=lambda x: (x["response_timestamp"], x["raw_cache_path"]))

    # 3. Scan all historical versions to reconstruct exact original_execution_seal and rejected attempts
    versions_dir = work / "versions"
    exclude_versions = {target_version} if target_version else set()
    hist_version_dirs = [
        d for d in sorted(versions_dir.iterdir())
        if d.is_dir() and (d / "bundle.json").exists() and d.name not in exclude_versions
    ]

    # Order historical versions chronologically by earliest file mtime in results/ (fallback bundle.json mtime)
    def version_sort_key(vdir: Path):
        rfiles = list((vdir / "results").rglob("*.json")) if (vdir / "results").exists() else []
        earliest = min((f.stat().st_mtime for f in rfiles), default=(vdir / "bundle.json").stat().st_mtime)
        return (earliest, vdir.name)

    hist_version_dirs.sort(key=version_sort_key)

    earliest_seal_for_canonical_resp = {}
    rejected_attempts = []
    version_inventory = []

    for vdir in hist_version_dirs:
        ver = vdir.name
        acc_count = 0
        rej_count = 0
        res_root = vdir / "results"
        if res_root.exists():
            for stage in p.STAGES:
                sdir = res_root / stage
                if not sdir.exists():
                    continue
                for f in sorted(sdir.glob("*.json")):
                    if f.name.endswith(".rejected.json"):
                        rej_count += 1
                        rj = json.loads(f.read_text(encoding="utf-8"))
                        rec = rj.get("record") or {}
                        canon = strip_evidence_keys(rec.get("response"))
                        if canon and canon not in earliest_seal_for_canonical_resp:
                            earliest_seal_for_canonical_resp[canon] = ver
                        matched_raw = raw_by_parsed.get(canon, [None])[-1] if canon else None
                        rejected_attempts.append({
                            "execution_seal": ver,
                            "stage": rec.get("stage", stage),
                            "study_id": rec.get("study_id", f.stem.split("_")[0]),
                            "batch_file": safe_relpath(f, root),
                            "batch_file_sha256": file_hash(f),
                            "validation_error": rj.get("validation_error", "UNKNOWN"),
                            "model": rec.get("model", "UNKNOWN"),
                            "model_settings": rec.get("model_settings", {}),
                            "prompt_hash": rec.get("prompt_hash", "UNKNOWN"),
                            "request_cache_key": matched_raw["request_cache_key"] if matched_raw else "UNMATCHED",
                            "raw_cache_path": matched_raw["raw_cache_path"] if matched_raw else "UNMATCHED",
                            "raw_cache_sha256": matched_raw["raw_cache_sha256"] if matched_raw else "UNAVAILABLE",
                            "token_usage": matched_raw["token_usage"] if matched_raw else {},
                        })
                    else:
                        acc_count += 1
                        rec = json.loads(f.read_text(encoding="utf-8"))
                        canon = strip_evidence_keys(rec.get("response"))
                        if canon and canon not in earliest_seal_for_canonical_resp:
                            earliest_seal_for_canonical_resp[canon] = ver
        version_inventory.append({
            "seal": ver,
            "accepted_batch_files": acc_count,
            "rejected_batch_files": rej_count,
        })

    # 4. Reconstruct provenance for all retained & pilot batches in target_version (or hist_version)
    active_results_dir = work / "versions" / (target_version if target_version else hist_version) / "results"
    manifest_records = []
    for stage in p.STAGES:
        expected_cfg = p.model_config(stage)
        stage_dir = active_results_dir / stage
        if not stage_dir.exists():
            continue
        for res_file in sorted(stage_dir.glob("*.json")):
            is_rejected = res_file.name.endswith(".rejected.json")
            data = json.loads(res_file.read_text(encoding="utf-8"))
            if is_rejected:
                rec = data.get("record", data)
                batch_status = "rejected_for_review"
                validation_error = data.get("validation_error", "")
            else:
                rec = data
                batch_status = "accepted"
                validation_error = None

            sid = rec["study_id"]
            study = studies[sid]
            doc = docs[study["pdf"]]
            batch_num = int(res_file.stem.split(".")[0].rsplit("_", 1)[1])
            group = {sg: target_bundle["authority"]["subgroups"][sg] for sg in sg_ids[(batch_num - 1) * 5:batch_num * 5]}
            expected_ph = p.digest(p.prompt_for(target_bundle, study, stage, group))

            # Canonicalize using raw stripped keys (page, quote, role) in case post-verification keys exist
            canon = strip_evidence_keys(rec.get("response"))

            raw_candidates = raw_by_parsed.get(canon, [])
            primary_raw = raw_candidates[-1] if raw_candidates else None
            ck = primary_raw["request_cache_key"] if primary_raw else "UNMATCHED"
            ck_attempts = raw_by_ck.get(ck, []) if ck != "UNMATCHED" else []

            orig_seal = earliest_seal_for_canonical_resp.get(canon) or rec.get("original_execution_seal") or hist_version
            if ck in HISTORICAL_REQUEST_ORIGIN_OVERRIDES:
                orig_seal = HISTORICAL_REQUEST_ORIGIN_OVERRIDES[ck]
            prompt_matches = (rec.get("prompt_hash") == expected_ph)
            cfg_matches = (rec.get("model") == expected_cfg["id"] and rec.get("model_settings") == expected_cfg)
            max_out_tok = (rec.get("model_settings") or {}).get("max_output_tokens")

            if sid in ("S05", "S12"):
                lineage_class = f"pilot_executed_under_{orig_seal[:8]}_revalidated_under_{(target_version or hist_version)[:8]}"
            elif orig_seal == hist_version and prompt_matches and cfg_matches:
                lineage_class = "executed_in_946a_64k"
            elif prompt_matches and cfg_matches:
                lineage_class = f"carried_over_identical_prompt_64k_from_{orig_seal[:8]}"
            elif max_out_tok == 32768:
                lineage_class = f"pilot_carried_over_32k_prompt_drift_from_{orig_seal[:8]}"
            else:
                lineage_class = f"pilot_carried_over_64k_prompt_drift_from_{orig_seal[:8]}"

            manifest_records.append({
                "study_id": sid,
                "batch_index": batch_num,
                "stage": stage,
                "batch_status": batch_status,
                "validation_error": validation_error,
                "split": study["split"],
                "building_scope": study["building_scope"],
                "retained_in_seal": target_version if target_version else hist_version,
                "imported_from_version": rec.get("imported_from_version"),
                "revalidated_under": target_version if target_version else hist_version,
                "original_execution_seal": orig_seal,
                "lineage_class": lineage_class,
                "request_cache_key": ck,
                "cache_entry_meta": cache_meta_by_ck.get(ck, {}),
                "model_requested": rec["model"],
                "model_returned_version": primary_raw["model_version"] if primary_raw else rec["model"],
                "model_settings": rec.get("model_settings", {}),
                "max_output_tokens_setting": max_out_tok,
                "settings_match_current_seal": cfg_matches,
                "prompt_hash": rec["prompt_hash"],
                "expected_current_prompt_hash": expected_ph,
                "prompt_matches_current_seal": prompt_matches,
                "record_hash": rec.get("record_hash") or data.get("rejected_hash", "UNAVAILABLE"),
                "result_file_path": safe_relpath(res_file, root),
                "result_file_sha256": file_hash(res_file),
                "raw_cache_path": primary_raw["raw_cache_path"] if primary_raw else "UNMATCHED",
                "raw_cache_sha256": primary_raw["raw_cache_sha256"] if primary_raw else "UNAVAILABLE",
                "response_id": primary_raw["response_id"] if primary_raw else "UNAVAILABLE",
                "response_timestamp": primary_raw["response_timestamp"] if primary_raw else "UNAVAILABLE",
                "finish_reason": primary_raw["finish_reason"] if primary_raw else "UNKNOWN",
                "attempt_count_for_request": len(ck_attempts),
                "all_attempts_for_request": [
                    {
                        "raw_cache_path": att["raw_cache_path"],
                        "raw_cache_sha256": att["raw_cache_sha256"],
                        "response_id": att["response_id"],
                        "response_timestamp": att["response_timestamp"],
                        "finish_reason": att["finish_reason"],
                        "token_usage": att["token_usage"],
                    }
                    for att in ck_attempts
                ],
                "source_pdf_path": doc["path"],
                "source_pdf_sha256": doc["sha256"],
                "token_usage": primary_raw["token_usage"] if primary_raw else {},
                "subgroups_evaluated": [a["subgroup"] for a in rec["response"]["assessments"]],
                "subgroup_scores": {a["subgroup"]: a["score"] for a in rec["response"]["assessments"]},
            })

    # 5. Summarise all raw provider requests (including unretained/truncated/retry calls)
    retained_cks = {r["request_cache_key"] for r in manifest_records if r["request_cache_key"] != "UNMATCHED"}
    raw_request_ledger = []
    for ck, attempts in sorted(raw_by_ck.items()):
        cmeta = cache_meta_by_ck.get(ck, {})
        raw_request_ledger.append({
            "request_cache_key": ck,
            "label": cmeta.get("label", ""),
            "model": cmeta.get("model") or attempts[-1]["model_version"],
            "retained_in_946a": ck in retained_cks,
            "attempt_count": len(attempts),
            "finish_reasons": [a["finish_reason"] for a in attempts],
            "attempts": [
                {
                    "raw_cache_path": a["raw_cache_path"],
                    "raw_cache_sha256": a["raw_cache_sha256"],
                    "response_id": a["response_id"],
                    "response_timestamp": a["response_timestamp"],
                    "model_version": a["model_version"],
                    "finish_reason": a["finish_reason"],
                    "token_usage": a["token_usage"],
                }
                for a in attempts
            ],
        })

    # 6. Aggregate empirical token telemetry by model across all 212 raw calls and across retained batches
    def sum_usage(entries):
        agg = {
            "call_count": len(entries),
            "prompt_tokens": 0,
            "cached_prompt_tokens": 0,
            "uncached_prompt_tokens": 0,
            "candidates_tokens": 0,
            "thoughts_tokens": 0,
            "output_plus_thoughts_tokens": 0,
            "total_tokens": 0,
        }
        for e in entries:
            u = e["token_usage"]
            for k in agg:
                if k != "call_count":
                    agg[k] += int(u.get(k, 0))
        return agg

    raw_by_model = defaultdict(list)
    for e in all_raw_entries:
        model_key = "gemini-4-argon" if "argon" in e["model_version"] else "gemini-3.8-flash"
        raw_by_model[model_key].append(e)

    retained_by_stage = defaultdict(list)
    for r in manifest_records:
        retained_by_stage[r["stage"]].append(r)

    unmatched_batches = [r["result_file_path"] for r in manifest_records if r["raw_cache_path"] == "UNMATCHED"]
    assert not unmatched_batches, f"Unmatched retained batches: {unmatched_batches}"

    payload = {
        "manifest_historical_version": hist_version,
        "compared_target_version": target_version or hist_version,
        "total_historical_seals_indexed": len(version_inventory),
        "historical_seal_inventory": version_inventory,
        "total_retained_batches": len(manifest_records),
        "total_unique_request_cache_keys": len(raw_request_ledger),
        "total_raw_provider_responses": len(all_raw_entries),
        "total_retry_or_rerun_responses": len(all_raw_entries) - len(raw_request_ledger),
        "non_stop_raw_responses": [
            {
                "request_cache_key": e["request_cache_key"],
                "raw_cache_path": e["raw_cache_path"],
                "model_version": e["model_version"],
                "finish_reason": e["finish_reason"],
                "response_timestamp": e["response_timestamp"],
                "token_usage": e["token_usage"],
            }
            for e in all_raw_entries if e["finish_reason"] != "STOP"
        ],
        "total_rejected_batch_files_logged": len(rejected_attempts),
        "telemetry_summary_all_raw_calls": {m: sum_usage(v) for m, v in sorted(raw_by_model.items())},
        "telemetry_summary_retained_180_batches": {st: sum_usage(v) for st, v in sorted(retained_by_stage.items())},
        "batches": manifest_records,
        "rejected_attempts": rejected_attempts,
        "raw_request_ledger": raw_request_ledger,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote provenance manifest to {out_path}")
    print(f"  Retained batches linked: {len(manifest_records)} (0 unmatched)")
    print(f"  Unique request CKs:      {len(raw_request_ledger)}")
    print(f"  Raw provider responses:  {len(all_raw_entries)} (retries/reruns: {len(all_raw_entries) - len(raw_request_ledger)})")
    print(f"  Non-STOP raw responses:  {len(payload['non_stop_raw_responses'])}")
    print(f"  Rejected batch records:  {len(rejected_attempts)}")
    for m, stats in payload["telemetry_summary_all_raw_calls"].items():
        print(f"  [{m}] calls={stats['call_count']}, uncached_in={stats['uncached_prompt_tokens']:,}, "
              f"cached_in={stats['cached_prompt_tokens']:,}, out={stats['candidates_tokens']:,}, "
              f"thoughts={stats['thoughts_tokens']:,}")


if __name__ == "__main__":
    main()
