"""loglens core: streaming pattern clustering and spike detection for big logs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

# Normalization: variable parts of a line collapse so that 5000 occurrences of
# the same error become one template with a count.
NORMALIZERS = [
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<uuid>"),
    (re.compile(r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b"), "<ip>"),
    (re.compile(r"\b0x[0-9a-fA-F]{6,}\b"), "<hex>"),
    (re.compile(r"\b[0-9a-f]{16,}\b", re.I), "<hash>"),
    # last: every remaining digit run collapses (uuid/ip/hex/hash already consumed)
    (re.compile(r"\d+"), "<n>"),
    (re.compile(r'"[^"]{0,200}"'), '"…"'),
]

TS_PATTERNS = [
    re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?"),
    re.compile(r"\[\d{2}/\w{3}/\d{4}:\d{2}:\d{2}:\d{2}"),
    re.compile(r"\d{2}:\d{2}:\d{2}(?:\.\d+)?"),
]

SEVERITY = re.compile(
    r"\b(TRACE|DEBUG|INFO|NOTICE|WARN(?:ING)?|ERROR|ERR|CRITICAL|CRIT|FATAL|PANIC)\b", re.I)

BUCKETS = 30


@dataclass
class Template:
    pattern: str
    count: int = 0
    first_line: int = 0
    last_line: int = 0
    severity: str = ""
    sample: str = ""


@dataclass
class Scan:
    path: str = ""
    lines: int = 0
    bytes_read: int = 0
    timeframe: str = ""
    severities: dict[str, int] = field(default_factory=dict)
    templates: list[Template] = field(default_factory=list)

    def top(self, n: int) -> list[Template]:
        return sorted(self.templates, key=lambda t: -t.count)[:n]

    def counts(self) -> dict[str, int]:
        return {k: v for k, v in self.severities.items() if v}


def normalize(line: str) -> str:
    for regex, replacement in NORMALIZERS:
        line = regex.sub(replacement, line)
    return line.strip()[:220]


def severity_of(line: str) -> str:
    m = SEVERITY.search(line)
    if not m:
        return ""
    token = m.group(1).upper()
    if token == "ERR":
        return "ERROR"
    if token == "CRIT":
        return "CRITICAL"
    if token == "WARN":
        return "WARNING"
    return token


def extract_ts(line: str) -> str | None:
    for p in TS_PATTERNS:
        m = p.search(line)
        if m:
            return m.group(0).strip("[]")
    return None


def scan(path: str | Path) -> Scan:
    """Stream the file line by line; memory holds templates, not the log."""
    result = Scan(path=str(path))
    counts: dict[str, Template] = {}
    first_ts = last_ts = None
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for line_no, line in enumerate(fh, 1):
            result.lines += 1
            result.bytes_read += len(line.encode("utf-8", "replace"))
            ts = extract_ts(line)
            if ts:
                first_ts = first_ts or ts
                last_ts = ts
            sev = severity_of(line)
            if sev:
                result.severities[sev] = result.severities.get(sev, 0) + 1
            key = normalize(line)
            if not key:
                key = "<blank>"
            tmpl = counts.get(key)
            if tmpl is None:
                counts[key] = Template(key, 1, line_no, line_no, sev, line.strip()[:220])
            else:
                tmpl.count += 1
                tmpl.last_line = line_no
    result.templates = list(counts.values())
    if first_ts and last_ts and first_ts != last_ts:
        result.timeframe = f"{first_ts} … {last_ts}"
    elif first_ts:
        result.timeframe = first_ts
    return result


def spikes(path: str | Path, buckets: int = BUCKETS) -> dict:
    """Error/broken-template counts across time buckets (by timestamp) or line ranges."""
    per_bucket: dict[int, int] = {}
    labels: dict[int, str] = {}
    total = 0
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        raw = []
        for line in fh:
            total += 1
            raw.append((extract_ts(line) or "", severity_of(line) or
                        ("ERR" if re.search(r"\b(error|fail|exception)\b", line, re.I) else "")))
    if not total:
        return {"buckets": [], "total": 0}
    has_ts = any(ts for ts, _ in raw)
    by_idx: dict[int, int] = {}
    if has_ts:
        for i, (ts, _) in enumerate(raw):
            by_idx.setdefault(ts, i)
        ordered = [ts for ts, _ in sorted(by_idx.items(), key=lambda kv: kv[1])]
        index_of = {ts: i for i, ts in enumerate(ordered)}
        for ts, sev in raw:
            if not sev or sev in ("INFO", "DEBUG", "TRACE"):
                continue
            b = index_of[ts] * buckets // max(1, len(ordered))
            per_bucket[b] = per_bucket.get(b, 0) + 1
            labels.setdefault(b, ts)
    else:
        chunk = max(1, total // buckets)
        for i, (_, sev) in enumerate(raw):
            if not sev or sev in ("INFO", "DEBUG", "TRACE"):
                continue
            b = i // chunk
            per_bucket[b] = per_bucket.get(b, 0) + 1
            labels.setdefault(b, f"lines {b * chunk + 1}-{(b + 1) * chunk}")
    out = [{"bucket": b, "label": labels.get(b, str(b)), "problems": n}
           for b, n in sorted(per_bucket.items())]
    return {"buckets": out, "total_lines": total, "total_problems": sum(per_bucket.values())}
