"""Small shared helpers: paths, hashing, JSON IO, logging."""
import hashlib
import json
import logging
import os
import re
import sys
import time
import tempfile
from pathlib import Path

LOG = logging.getLogger("markpipe")


def setup_logging(verbose=False, logfile=None):
    LOG.setLevel(logging.DEBUG if verbose else logging.INFO)
    LOG.handlers[:] = []
    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(message)s", "%H:%M:%S")
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(fmt)
    LOG.addHandler(h)
    if logfile:
        Path(logfile).parent.mkdir(parents=True, exist_ok=True)
        f = logging.FileHandler(logfile, encoding="utf-8")
        f.setFormatter(fmt)
        f.setLevel(logging.DEBUG)
        LOG.addHandler(f)

    # The SDK warns on every call that the response carried a thought_signature
    # part alongside the text. That is expected with thinking enabled and the
    # JSON we want is returned correctly, so it would only add one noise line
    # per call to a log with thousands of them.
    for noisy in ("google_genai.types", "google_genai", "google.genai"):
        logging.getLogger(noisy).setLevel(logging.ERROR)
    return LOG


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def combined_digest(digests):
    """Stable single digest for a submission made of several files.

    The staff scorer requires exactly one 64-hex `source_file_sha256`. When a
    student uploaded several PDFs we hash the sorted per-file digests, so the
    value is reproducible and every individual digest is still recorded in the
    submission record.
    """
    joined = "".join(sorted(digests))
    return hashlib.sha256(joined.encode("ascii")).hexdigest()


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + '.', suffix='.tmp', dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(obj, fh, indent=2, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return path


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def slugify(text, maxlen=60):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", str(text)).strip("_")
    return s[:maxlen] or "x"


def extract_json(text):
    """Pull a JSON object/array out of a model response.

    We ask for response_mime_type=application/json, but stay tolerant of a
    fenced block or leading prose so a good answer is never thrown away.
    """
    if text is None:
        raise ValueError("empty model response")
    text = text.strip()
    if not text:
        raise ValueError("empty model response")
    try:
        return json.loads(text)
    except Exception:
        pass
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        try:
            return json.loads(fence.group(1).strip())
        except Exception:
            pass
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        end = text.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except Exception:
                continue
    raise ValueError("could not parse JSON from model response: %r" % text[:300])


class Timer(object):
    def __init__(self, label):
        self.label = label

    def __enter__(self):
        self.t0 = time.time()
        return self

    def __exit__(self, *exc):
        LOG.debug("%s took %.1fs", self.label, time.time() - self.t0)
        return False
