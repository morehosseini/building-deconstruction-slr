"""Quota pacing against the Gemini API's real limits.

The binding constraint for this workload is TOKENS per minute, not requests.
A scoring call carries the staff controls plus every page image - about 40k
tokens - so a 3M TPM tier allows only ~74 calls/minute even though the same
tier permits 2,000 requests/minute. Pacing on request rate alone starves the
run while still overshooting TPM, which is what produces sustained 429s.

Cached tokens still count toward TPM. Context caching cuts cost, not quota.

Quotas are also per PROJECT, not per API key: extra keys on the same project
share one budget and do not multiply throughput. The limiter is therefore
shared across keys by default.
"""
import collections
import threading
import time

from .util import LOG


class QuotaLimiter(object):
    def __init__(self, rpm, tpm, rpd=None, estimated_tokens=40000, label="project"):
        self.max_rpm = float(rpm)
        self.max_tpm = float(tpm)
        self.max_rpd = float(rpd) if rpd else None
        self.rpm = float(rpm)
        self.tpm = float(tpm)
        self.label = label
        self.estimate = float(estimated_tokens)
        self._req = collections.deque()          # request timestamps (60s window)
        self._tok = collections.deque()          # [ts, tokens] (60s window)
        self._day = collections.deque()          # request timestamps (24h window)
        self._lock = threading.Lock()
        self._last_penalty = 0.0
        self._last_raise = time.time()
        self.penalties = 0
        self.waited_seconds = 0.0
        self.observed_calls = 0

    # --- window maintenance --------------------------------------------------
    def _prune(self, now):
        cutoff = now - 60.0
        while self._req and self._req[0] < cutoff:
            self._req.popleft()
        while self._tok and self._tok[0][0] < cutoff:
            self._tok.popleft()
        if self.max_rpd is not None:
            day = now - 86400.0
            while self._day and self._day[0] < day:
                self._day.popleft()

    def _tokens_in_window(self):
        return sum(entry[1] for entry in self._tok)

    # --- admission -----------------------------------------------------------
    def acquire(self):
        """Block until another call fits inside every window. Returns a handle
        whose token count must be corrected later via `settle`."""
        # Reserve slightly above the running average so a burst of
        # larger-than-average calls cannot overshoot before it is measured.
        reserve = self.estimate * 1.1
        if reserve > self.max_tpm:
            raise ValueError('Estimated request cannot fit maximum TPM; reduce context or increase quota')
        waited = 0.0
        while True:
            with self._lock:
                now = time.time()
                self._prune(now)
                if now - self._last_penalty > 60 and now - self._last_raise > 30 \
                        and self.tpm < self.max_tpm:
                    self.tpm = min(self.max_tpm, self.tpm * 1.15)
                    self._last_raise = now
                    LOG.debug("quota %s: raising to %.0f tpm", self.label, self.tpm)

                if self.max_rpd is not None and len(self._day) >= self.max_rpd:
                    wait = max(1.0, 86400.0 - (now - self._day[0]))
                    LOG.warning("quota %s: daily request limit reached; waiting %.0f min",
                                self.label, wait / 60.0)
                elif len(self._req) >= self.rpm:
                    wait = max(0.05, 60.0 - (now - self._req[0]))
                elif self._tokens_in_window() + reserve > self.tpm:
                    if not self._tok and reserve > self.tpm:
                        raise ValueError('Request exceeds reduced TPM budget; retry later with adjusted quota')
                    wait = max(0.05, 60.0 - (now - self._tok[0][0])) if self._tok else 0.5
                else:
                    entry = [now, reserve]
                    self._req.append(now)
                    self._tok.append(entry)
                    if self.max_rpd is not None:
                        self._day.append(now)
                    self.waited_seconds += waited
                    return entry
            time.sleep(min(wait, 5.0))
            waited += min(wait, 5.0)

    def settle(self, handle, actual_tokens):
        """Replace the reservation with what the call actually cost."""
        if handle is None or not actual_tokens:
            return
        with self._lock:
            handle[1] = float(actual_tokens)
            self.observed_calls += 1
            # Exponential moving average of real cost, used for the next reserve.
            self.estimate += (float(actual_tokens) - self.estimate) * 0.2

    def release(self, handle):
        """Drop a reservation for a call that never reached the server."""
        if handle is None:
            return
        with self._lock:
            handle[1] = 0.0

    def penalise(self):
        """The server rejected us: lower the token target, not the request rate."""
        with self._lock:
            now = time.time()
            if now - self._last_penalty < 3.0:
                return self.tpm
            previous = self.tpm
            self.tpm = max(self.max_tpm * 0.1, self.tpm * 0.75)
            self._last_penalty = now
            self.penalties += 1
            LOG.info("quota %s: 429 received, easing %.2fM -> %.2fM tokens/min",
                     self.label, previous / 1e6, self.tpm / 1e6)
            return self.tpm

    def stats(self):
        with self._lock:
            now = time.time()
            self._prune(now)
            return {
                "target_tpm": int(self.tpm),
                "max_tpm": int(self.max_tpm),
                "tokens_last_60s": int(self._tokens_in_window()),
                "requests_last_60s": len(self._req),
                "requests_last_24h": len(self._day) if self.max_rpd else None,
                "avg_tokens_per_call": int(self.estimate),
                "throttle_events": self.penalties,
                "seconds_spent_waiting": round(self.waited_seconds, 1),
            }
