"""Gemini client: retries, response caching, key pinning and page uploads.

Two details that matter for this pipeline:

* Files API handles belong to the API key that uploaded them, so every call for
  a given student is pinned to one key. Different students use different keys,
  which is where the parallelism comes from.
* Independent assessment passes must not collide in the response cache, so the
  pass index is part of the cache key. Re-running a batch reuses answers;
  asking for a 6th pass genuinely asks the model again.
"""
import copy
import hashlib
import json
import math
import os
import random
import re
import tempfile
import threading
import time
import mimetypes
import uuid
from pathlib import Path

from google import genai
from google.genai import types

from .ratelimit import QuotaLimiter
from .util import LOG, extract_json, sha256_bytes

RETRYABLE = ("429", "500", "502", "503", "504", "RESOURCE_EXHAUSTED",
             "UNAVAILABLE", "INTERNAL", "DEADLINE_EXCEEDED", "timeout",
             # An accepted request that comes back with no body at all. Often
             # transient; losing a whole submission to one is not acceptable,
             # so retry with backoff and surface it only if it keeps happening.
             "empty model response")


class BudgetExceededError(RuntimeError):
    """Raised before dispatching a provider request when attempt or USD ceilings are reached."""


def compute_usage_cost_usd(usage, pricing):
    if not pricing:
        return 0.0
    prompt_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
    cached_tok = int(getattr(usage, "cached_content_token_count", 0) or 0)
    uncached_tok = max(0, prompt_tok - cached_tok)
    cand_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
    thought_tok = int(getattr(usage, "thoughts_token_count", 0) or 0)
    return (
        (uncached_tok / 1_000_000.0) * float(pricing["uncached_input_usd_per_1m"])
        + (cached_tok / 1_000_000.0) * float(pricing["cached_input_usd_per_1m"])
        + ((cand_tok + thought_tok) / 1_000_000.0) * float(pricing["output_plus_thoughts_usd_per_1m"])
    )


def estimate_upper_bound_input_tokens(system, parts, schema):
    sys_tokens = math.ceil(len((system or "").encode("utf-8")) / 2.8)
    schema_tokens = (
        math.ceil(len(json.dumps(schema, sort_keys=True).encode("utf-8")) / 2.5) + 1500
        if schema is not None else 500
    )
    str_page_markers = sum(p.count("[PDF PAGE ") for p in parts if isinstance(p, str))
    part_tokens = 0
    for p in parts:
        if isinstance(p, str):
            part_tokens += math.ceil(len(p.encode("utf-8")) / 2.8)
        elif getattr(p, "inline_data", None) is not None:
            mime = str(getattr(p.inline_data, "mime_type", "") or "")
            raw = getattr(p.inline_data, "data", b"") or b""
            if "pdf" in mime.lower():
                pdf_pages = str_page_markers or len(re.findall(rb"/Type\s*/Page\b", raw)) or 1
                part_tokens += pdf_pages * 2600
            else:
                part_tokens += max(3000, math.ceil(len(raw) / 500))
        else:
            part_tokens += 3000
    return sys_tokens + schema_tokens + part_tokens


class BudgetLedger(object):
    """Enforces hard provider-attempt and USD spending ceilings (in-memory and optional atomic JSON file)."""

    def __init__(self, path=None, max_attempts=None, max_cost_usd=None):
        if max_attempts is not None and int(max_attempts) < 1:
            raise ValueError("max_attempts must be >= 1")
        if max_cost_usd is not None and float(max_cost_usd) <= 0.0:
            raise ValueError("max_cost_usd must be > 0")
        self.path = Path(path) if path is not None else None
        self.max_attempts = int(max_attempts) if max_attempts is not None else None
        self.max_cost_usd = float(max_cost_usd) if max_cost_usd is not None else None
        self._lock = threading.Lock()
        self._state = self._load_or_init()

    def _default_state(self):
        return {
            "max_attempts": self.max_attempts,
            "max_cost_usd": self.max_cost_usd,
            "provider_attempts": 0,
            "completed_responses": 0,
            "failed_transport_attempts": 0,
            "settled_cost_usd": 0.0,
            "unsettled_reserved_usd": 0.0,
            "tokens": {
                "prompt_tokens": 0,
                "uncached_prompt_tokens": 0,
                "cached_prompt_tokens": 0,
                "output_tokens": 0,
                "thought_tokens": 0,
            },
            "events": [],
        }

    def _save(self, state):
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(mode="w", dir=self.path.parent, delete=False, encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
            f.write("\n")
            tmp = f.name
        os.replace(tmp, self.path)

    def _load_or_init(self):
        if self.path is not None and self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if self.max_attempts is not None:
                if state.get("max_attempts") is not None and int(state["max_attempts"]) != self.max_attempts:
                    raise ValueError(
                        "Budget ledger max_attempts (%s) conflicts with requested max_attempts (%s)"
                        % (state.get("max_attempts"), self.max_attempts)
                    )
                state["max_attempts"] = self.max_attempts
            if self.max_cost_usd is not None:
                if state.get("max_cost_usd") is not None and abs(float(state["max_cost_usd"]) - self.max_cost_usd) > 1e-9:
                    raise ValueError(
                        "Budget ledger max_cost_usd (%s) conflicts with requested max_cost_usd (%s)"
                        % (state.get("max_cost_usd"), self.max_cost_usd)
                    )
                state["max_cost_usd"] = self.max_cost_usd
            self._save(state)
            return state
        state = self._default_state()
        self._save(state)
        return state

    def _refresh(self):
        if self.path is not None and self.path.exists():
            self._state = json.loads(self.path.read_text(encoding="utf-8"))
        return self._state

    def reserve_before_attempt(self, model, label, reserved_cost_usd):
        with self._lock:
            state = self._refresh()
            cap_attempts = state.get("max_attempts")
            if cap_attempts is None:
                cap_attempts = self.max_attempts
            if cap_attempts is not None and state["provider_attempts"] + 1 > int(cap_attempts):
                raise BudgetExceededError(
                    "Provider attempt limit (%d) reached (used=%d); blocking attempt for %s"
                    % (int(cap_attempts), state["provider_attempts"], label)
                )
            cap_cost = state.get("max_cost_usd")
            if cap_cost is None:
                cap_cost = self.max_cost_usd
            committed_usd = float(state["settled_cost_usd"]) + float(state["unsettled_reserved_usd"])
            if cap_cost is not None:
                if committed_usd >= float(cap_cost) or (committed_usd + float(reserved_cost_usd)) > float(cap_cost) + 1e-12:
                    raise BudgetExceededError(
                        "USD spending ceiling ($%.4f) would be exceeded (committed=$%.4f, next_upper_bound=$%.4f); blocking %s"
                        % (float(cap_cost), committed_usd, float(reserved_cost_usd), label)
                    )
            attempt_id = uuid.uuid4().hex
            state["provider_attempts"] += 1
            state["unsettled_reserved_usd"] = round(float(state["unsettled_reserved_usd"]) + float(reserved_cost_usd), 8)
            state["events"].append({
                "attempt_id": attempt_id,
                "attempt_number": state["provider_attempts"],
                "model": model,
                "label": label,
                "status": "in_flight",
                "reserved_cost_usd": round(float(reserved_cost_usd), 8),
            })
            self._save(state)
            return attempt_id

    def settle_response(self, attempt_id, reserved_cost_usd, usage, actual_cost_usd, finish_reason):
        with self._lock:
            state = self._refresh()
            state["unsettled_reserved_usd"] = round(
                max(0.0, float(state["unsettled_reserved_usd"]) - float(reserved_cost_usd)), 8
            )
            state["settled_cost_usd"] = round(float(state["settled_cost_usd"]) + float(actual_cost_usd), 8)
            state["completed_responses"] += 1
            if usage is not None:
                pt = int(getattr(usage, "prompt_token_count", 0) or 0)
                ct = int(getattr(usage, "cached_content_token_count", 0) or 0)
                ot = int(getattr(usage, "candidates_token_count", 0) or 0)
                tt = int(getattr(usage, "thoughts_token_count", 0) or 0)
                tok = state["tokens"]
                tok["prompt_tokens"] += pt
                tok["uncached_prompt_tokens"] += max(0, pt - ct)
                tok["cached_prompt_tokens"] += ct
                tok["output_tokens"] += ot
                tok["thought_tokens"] += tt
            for ev in reversed(state["events"]):
                if ev.get("attempt_id") == attempt_id:
                    ev["status"] = "settled"
                    ev["finish_reason"] = finish_reason
                    ev["actual_cost_usd"] = round(float(actual_cost_usd), 8)
                    break
            self._save(state)
            cap_cost = state.get("max_cost_usd")
            if cap_cost is None:
                cap_cost = self.max_cost_usd
            if cap_cost is not None and float(state["settled_cost_usd"]) > float(cap_cost) + 1e-9:
                raise BudgetExceededError(
                    "USD spending ceiling ($%.4f) exceeded after settlement ($%.4f)"
                    % (float(cap_cost), float(state["settled_cost_usd"]))
                )

    def release_failed_transport(self, attempt_id, reserved_cost_usd, error_text):
        with self._lock:
            state = self._refresh()
            state["unsettled_reserved_usd"] = round(
                max(0.0, float(state["unsettled_reserved_usd"]) - float(reserved_cost_usd)), 8
            )
            state["failed_transport_attempts"] += 1
            for ev in reversed(state["events"]):
                if ev.get("attempt_id") == attempt_id:
                    ev["status"] = "transport_error"
                    ev["error"] = str(error_text)[:240]
                    break
            self._save(state)

    def attempts_exhausted(self):
        with self._lock:
            state = self._refresh()
            cap_attempts = state.get("max_attempts")
            if cap_attempts is None:
                cap_attempts = self.max_attempts
            return cap_attempts is not None and state["provider_attempts"] >= int(cap_attempts)

    def snapshot(self):
        with self._lock:
            state = self._refresh()
            return copy.deepcopy({k: v for k, v in state.items() if k != "events"})


def collect_keys():
    keys = []
    for name in ("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        if os.environ.get(name):
            keys.append(os.environ[name])
    i = 2
    while os.environ.get("GEMINI_API_KEY_%d" % i):
        keys.append(os.environ["GEMINI_API_KEY_%d" % i])
        i += 1
    seen, unique = set(), []
    for k in keys:
        if k not in seen:
            seen.add(k)
            unique.append(k)
    if not unique:
        raise SystemExit("No API key found. See marking_pipeline/.env.example")
    return unique


def _clean_schema(s):
    if isinstance(s, dict):
        return {k: _clean_schema(v) for k, v in s.items() if k not in ("additionalProperties", "additional_properties")}
    elif isinstance(s, list):
        return [_clean_schema(x) for x in s]
    return s


class GeminiClient(object):
    def __init__(self, model_cfg, cache_dir, keys=None, pricing=None,
                 max_attempts=None, max_cost_usd=None, budget_file=None,
                 max_retries_override=None):
        self.cfg = model_cfg
        self.model = model_cfg["id"]
        if max_cost_usd is not None and not pricing:
            raise ValueError("Model pricing rates are required when max_cost_usd is enabled")
        self.pricing = copy.deepcopy(pricing) if pricing else None
        self.max_retries_override = max_retries_override
        self.budget = BudgetLedger(path=budget_file, max_attempts=max_attempts, max_cost_usd=max_cost_usd)
        self.keys = keys or collect_keys()
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._clients = {}
        self._lock = threading.Lock()
        self._upload_cache = {}
        self._context_caches = {}
        self._context_payloads = {}
        self._evidence = {}
        # Cap simultaneous in-flight requests across the whole batch. Without
        # this, students x units x passes can put ~100 requests in flight and
        # spend the run being rate-limited and retried.
        self._slots = threading.Semaphore(int(model_cfg.get("max_concurrent_requests", 24)))
        # Gemini quotas are per PROJECT, not per key: keys on the same project
        # share one budget. One shared limiter unless told otherwise.
        def make(label):
            return QuotaLimiter(
                rpm=float(model_cfg.get("requests_per_minute", 1800)),
                tpm=float(model_cfg.get("tokens_per_minute", 2700000)),
                rpd=model_cfg.get("requests_per_day"),
                estimated_tokens=float(model_cfg.get("estimated_tokens_per_call", 40000)),
                label=label)
        if model_cfg.get("quota_is_per_key"):
            self._limiters = dict((k, make("key%d" % i)) for i, k in enumerate(self.keys, 1))
        else:
            shared = make("project")
            self._limiters = dict((k, shared) for k in self.keys)
        self.calls = 0
        self.provider_attempts = 0
        self.cache_hits = 0
        self.prompt_tokens = 0
        self.output_tokens = 0
        self.thought_tokens = 0
        self.cached_tokens = 0
        self.cost_usd = 0.0

    # --- key pinning ---------------------------------------------------------
    def set_evidence(self, pin, identity, force=False):
        with self._lock:
            self._evidence[pin] = (identity, uuid.uuid4().hex if force else 'replay')

    def key_for(self, pin):
        """Stable key choice for a student, so Files API handles stay valid."""
        idx = int(hashlib.sha256(str(pin).encode()).hexdigest(), 16) % len(self.keys)
        return self.keys[idx]

    def _client(self, key):
        with self._lock:
            if key not in self._clients:
                self._clients[key] = genai.Client(
                    api_key=key,
                    http_options=types.HttpOptions(timeout=self.cfg.get("request_timeout_s", 600) * 1000),
                )
            return self._clients[key]

    # --- page uploads --------------------------------------------------------
    def upload_pages(self, pin, image_paths):
        """Upload page images once per (student, key); return reusable Parts.

        Returns None if uploading is unavailable, so the caller falls back to
        inline bytes.
        """
        key = self.key_for(pin)
        client = self._client(key)
        parts = []
        for path in image_paths:
            path = str(path)
            ck = (key, path, os.path.getmtime(path))
            with self._lock:
                cached = self._upload_cache.get(ck)
            if cached is None:
                try:
                    fh = client.files.upload(file=path,
                                             config={"mime_type": image_mime(path)})
                    cached = (fh.uri, fh.mime_type or image_mime(path))
                except Exception as exc:
                    LOG.warning("Files API upload failed (%s); using inline bytes", exc)
                    return None
                with self._lock:
                    self._upload_cache[ck] = cached
            parts.append(types.Part.from_uri(file_uri=cached[0], mime_type=cached[1]))
        return parts

    # --- explicit context caching -------------------------------------------
    def create_context_cache(self, pin, system, parts, ttl_seconds=3600):
        """Cache the system instruction + page images once per student.

        Every scoring call for a student repeats the same ~40k tokens of staff
        controls and page images. Caching them makes the repeat cheap and fast.
        Returns a cache name, or None if caching is unavailable - callers must
        work either way.
        """
        with self._lock:
            self._context_payloads[pin] = (system, list(parts))
            if pin in self._context_caches:
                return self._context_caches[pin]
        client = self._client(self.key_for(pin))
        try:
            cache = client.caches.create(
                model=self.model,
                config=types.CreateCachedContentConfig(
                    system_instruction=system,
                    contents=[types.Content(role="user", parts=list(parts))],
                    ttl="%ds" % int(ttl_seconds),
                    display_name="markpipe-%s" % pin,
                ),
            )
            with self._lock:
                self._context_caches[pin] = cache.name
            LOG.info("context cache created for %s (%s tokens)", pin,
                     getattr(getattr(cache, "usage_metadata", None), "total_token_count", "?"))
            return cache.name
        except Exception as exc:
            LOG.warning("context caching unavailable for %s (%s); sending full context each call",
                        pin, str(exc)[:200])
            with self._lock:
                self._context_caches[pin] = None
            return None

    def delete_context_cache(self, pin):
        with self._lock:
            name = self._context_caches.pop(pin, None)
            self._context_payloads.pop(pin, None)
        if not name:
            return
        try:
            self._client(self.key_for(pin)).caches.delete(name=name)
        except Exception as exc:
            LOG.debug("cache delete failed for %s: %s", pin, exc)

    # --- generation ----------------------------------------------------------
    def _config(self, system, temperature, schema, thinking_level, max_tokens,
                cached_content=None):
        extra = {}
        if thinking_level:
            extra = {"generationConfig": {"thinkingConfig": {"thinkingLevel": thinking_level}}}
        kwargs = dict(
            temperature=temperature,
            max_output_tokens=max_tokens or self.cfg.get("max_output_tokens", 32768),
            response_mime_type="application/json",
            media_resolution=types.MediaResolution.MEDIA_RESOLUTION_HIGH,
        )
        if cached_content:
            # The cache already carries the system instruction and page images.
            kwargs["cached_content"] = cached_content
        else:
            kwargs["system_instruction"] = system
        if schema is not None:
            # The SDK rewrites the schema in place (it adds propertyOrdering).
            # Our schemas are module-level constants shared across threads, so a
            # mutated one makes later calls fail validation - always send a copy.
            # Clean OpenAPI-incompatible fields (e.g. additionalProperties) for the API payload.
            kwargs["response_schema"] = _clean_schema(copy.deepcopy(schema))
        if extra:
            kwargs["http_options"] = types.HttpOptions(
                timeout=self.cfg.get("request_timeout_s", 600) * 1000, extra_body=extra)
        else:
            kwargs["http_options"] = types.HttpOptions(
                timeout=self.cfg.get("request_timeout_s", 600) * 1000)
        budget = self.cfg.get("thinking_budget")
        if budget and not thinking_level:
            kwargs["thinking_config"] = types.ThinkingConfig(thinking_budget=budget)
        return types.GenerateContentConfig(**kwargs)

    def _cache_key(self, pin, system, parts_digest, temperature, variant, thinking_level, schema_name):
        # `pin` (the student) MUST be part of the key: when page images live in a
        # context cache they are not in parts_digest, so without it two students
        # asking the same question would share a cached answer.
        blob = json.dumps([str(pin), self.model, system, parts_digest, temperature, variant,
                           thinking_level, schema_name, self._evidence.get(pin), self.cfg], sort_keys=True)
        return sha256_bytes(blob.encode("utf-8"))

    def generate_json(self, pin, system, parts, temperature=0.0, variant=0,
                      thinking_level=None, schema=None, schema_name="", max_tokens=None,
                      label="", use_cache=True, cached_content=None):
        if thinking_level is None:
            thinking_level = self.cfg.get("thinking_level", "high")
        if cached_content and (pin not in self._evidence or pin not in self._context_payloads):
            raise ValueError('Cached request has no registered source identity/full evidence payload')
        """One JSON-returning call, with disk cache and retry/backoff."""
        digest_src = []
        for p in parts:
            if isinstance(p, str):
                digest_src.append(p)
            elif getattr(p, "file_data", None) is not None:
                digest_src.append(str(p.file_data.file_uri))
            elif getattr(p, "inline_data", None) is not None:
                digest_src.append(sha256_bytes(p.inline_data.data))
            else:
                digest_src.append(str(p))
        parts_digest = sha256_bytes("\n".join(digest_src).encode("utf-8"))
        schema_identity = json.dumps([schema_name, schema, max_tokens], sort_keys=True)
        ck = self._cache_key(pin, system, parts_digest, temperature, variant,
                             thinking_level, schema_identity)
        cache_file = self.cache_dir / (ck + ".json")
        if use_cache and cache_file.exists():
            try:
                with self._lock:
                    self.cache_hits += 1
                return json.loads(cache_file.read_text(encoding="utf-8"))["parsed"]
            except Exception:
                pass

        key = self.key_for(pin)
        client = self._client(key)
        config = self._config(system, temperature, schema, thinking_level, max_tokens,
                              cached_content=cached_content)
        attempts = int(self.max_retries_override if self.max_retries_override is not None else self.cfg.get("max_retries", 6))
        if attempts < 1:
            raise ValueError("max_retries must be >= 1")
        max_out_tokens = int(max_tokens or self.cfg.get("max_output_tokens", 32768))
        last = None
        for attempt in range(attempts):
            limiter = self._limiters[key]
            handle = None
            limiter_settled = False
            attempt_id = None
            response_received = False
            est_in_tokens = estimate_upper_bound_input_tokens(system, parts, schema)
            if self.pricing:
                reserved_cost_usd = (
                    (est_in_tokens / 1_000_000.0) * float(self.pricing["uncached_input_usd_per_1m"])
                    + (max_out_tokens / 1_000_000.0) * float(self.pricing["output_plus_thoughts_usd_per_1m"])
                )
            else:
                reserved_cost_usd = 0.0
            try:
                with self._slots:
                    attempt_id = self.budget.reserve_before_attempt(self.model, label or self.model, reserved_cost_usd)
                    with self._lock:
                        self.provider_attempts += 1
                    handle = limiter.acquire()
                    resp = client.models.generate_content(model=self.model, contents=list(parts),
                                                          config=config)
                    response_received = True
                # Research adaptation: preserve each response before JSON parsing.
                raw_dir = self.cache_dir / "raw"
                raw_dir.mkdir(parents=True, exist_ok=True)
                raw_path = raw_dir / (ck + "_" + uuid.uuid4().hex + ".json")
                raw_path.write_text(resp.model_dump_json(), encoding="utf-8")
                candidates = resp.candidates or []
                finish = str(getattr(candidates[0], "finish_reason", "")) if candidates else ""
                usage = getattr(resp, "usage_metadata", None)
                if usage is not None:
                    p_tok = int(getattr(usage, "prompt_token_count", 0) or 0)
                    c_tok = int(getattr(usage, "cached_content_token_count", 0) or 0)
                    o_tok = int(getattr(usage, "candidates_token_count", 0) or 0)
                    t_tok = int(getattr(usage, "thoughts_token_count", 0) or 0)
                    actual_cost_usd = compute_usage_cost_usd(usage, self.pricing)
                else:
                    p_tok = c_tok = o_tok = t_tok = 0
                    actual_cost_usd = reserved_cost_usd
                # Settle quota and budget IMMEDIATELY upon receiving a response (even if truncated or non-STOP).
                limiter.settle(handle, p_tok + o_tok + t_tok)
                limiter_settled = True
                with self._lock:
                    self.calls += 1
                    self.prompt_tokens += p_tok
                    self.output_tokens += o_tok
                    self.thought_tokens += t_tok
                    self.cached_tokens += c_tok
                    self.cost_usd = round(self.cost_usd + actual_cost_usd, 8)
                self.budget.settle_response(attempt_id, reserved_cost_usd, usage, actual_cost_usd, finish)
                if not finish.endswith("STOP"):
                    raise ValueError("Incomplete provider response: " + finish)
                parsed = extract_json(resp.text)
                if use_cache:
                    cache_file.write_text(json.dumps({
                        "label": label, "model": self.model, "variant": variant,
                        "temperature": temperature, "parsed": parsed,
                    }, ensure_ascii=False), encoding="utf-8")
                return parsed
            except BudgetExceededError:
                if handle is not None and not limiter_settled:
                    limiter.release(handle)
                raise
            except Exception as exc:
                if attempt_id is not None and not response_received:
                    self.budget.release_failed_transport(attempt_id, reserved_cost_usd, str(exc))
                last = exc
                text = str(exc)
                if ("429" in text or "RESOURCE_EXHAUSTED" in text) and handle is not None and not limiter_settled:
                    limiter.penalise()
                    limiter.release(handle)   # rejected calls consumed no quota
                    limiter_settled = True
                elif handle is not None and not limiter_settled:
                    limiter.release(handle)
                    limiter_settled = True
                # A cached call can also fail by returning nothing at all: the
                # request is accepted, the response body is empty, and the same
                # call then fails identically on every retry. That cost one
                # ABPL20053 submission its entire assessment on 2026-09-06 -
                # the identical request sent inline succeeded every time. Treat
                # an empty or unparseable answer on a cached call as a cache
                # failure and fall back to the full context, rather than
                # retrying the same doomed request until the attempts run out.
                cache_suspect = ("CachedContent" in text or "cached_content" in text
                                 or "not found" in text.lower()
                                 or "empty model response" in text
                                 or "could not parse JSON" in text)
                if cached_content and cache_suspect:
                    LOG.warning("%s: context cache unusable (%s); retrying with full context",
                                label, text[:120])
                    cached_content = None
                    full_system, original_parts = self._context_payloads[pin]
                    if full_system != system:
                        raise ValueError('Context-cache system mismatch')
                    parts = list(original_parts) + list(parts)
                    config = self._config(system, temperature, schema, thinking_level,
                                          max_tokens, cached_content=None)
                    continue
                retryable = any(token in text for token in RETRYABLE) or "Incomplete provider response" in text
                if not retryable and "could not parse JSON" not in text:
                    LOG.error("%s: non-retryable %s: %s", label, type(exc).__name__, text[:300])
                    raise
                if attempt + 1 < attempts and self.budget.attempts_exhausted():
                    snap = self.budget.snapshot()
                    raise BudgetExceededError(
                        "Provider attempt limit (%s) reached after failed attempt (%s); blocking retry for %s"
                        % (snap.get("max_attempts"), text[:120], label or self.model)
                    )
                sleep = min(60.0, (2 ** attempt) + random.uniform(0, 1.5))
                LOG.warning("%s: attempt %d/%d failed (%s); retrying in %.1fs",
                            label, attempt + 1, attempts, text[:140], sleep)
                time.sleep(sleep)
        raise RuntimeError("%s: giving up after %d attempts: %s" % (label, attempts, last))

    def stats(self):
        return {"api_calls": self.calls,
                "provider_attempts": self.provider_attempts,
                "cache_hits": self.cache_hits,
                "prompt_tokens": self.prompt_tokens, "output_tokens": self.output_tokens,
                "thought_tokens": self.thought_tokens,
                "cached_tokens": self.cached_tokens,
                "cost_usd": round(self.cost_usd, 6),
                "budget": self.budget.snapshot(),
                "quota": dict((l.label, l.stats()) for l in
                              dict((id(x), x) for x in self._limiters.values()).values())}


def inline_parts(image_paths):
    parts = []
    for path in image_paths:
        parts.append(types.Part.from_bytes(data=Path(path).read_bytes(), mime_type=image_mime(path)))
    return parts


def image_mime(path):
    mime = mimetypes.guess_type(str(path))[0]
    if mime not in ('image/jpeg', 'image/png', 'image/webp'):
        raise ValueError('Unsupported image MIME type: %s' % path)
    return mime
