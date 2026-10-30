---
name: log-triage
description: Diagnose what happened in a huge log without reading it line by line — cluster lines into error templates with counts, find when incidents started, extract samples. Use whenever the user shares or points at a log file (server log, CI log, app log), says "look at the logs", "the app is throwing errors", "find what broke", "why is it failing", mentions grep'ing a big log, pastes a wall of repeated tracebacks, or asks "what's in this log", "when did it start failing", "how often does this error happen". Works on any text log of any size (streaming, memory-safe).
---

# Log triage

A 500 MB log cannot be read — not by a human, not by an agent with a finite context. But it doesn't need to be: logs are highly repetitive, and the real information is a handful of templates with counts and a timeline. This skill answers "what happened" from the shape of the log, not from reading it.

Install the CLI:

```bash
pip install loglens
```

## 1. Cluster first, read only the samples

```bash
loglens scan app.log
```

```text
lines    3,000 (222,367 bytes)
time     2026-10-30 09:00:00 … 2026-10-30 10:39:58
levels   INFO 1,999, DEBUG 579, WARNING 273, ERROR 149

  1,999×  L1-L2999  [INFO]
        2026-10-30 09:00:00 INFO request handled path=/api/lots/26 status=200 dur=37ms

  149×  L902-L1050  [ERROR]
        2026-10-30 09:30:02 ERROR api.db timeout after 30s query=select * from lots where id=491
```

Numbers, UUIDs, IPs, hashes and quoted strings are normalized away, so 3000 slightly-different lines collapse into a handful of templates with counts, line ranges and one real sample each. `--json` for agents; `--top N` to see more.

The reading order: **severity counts → the top ERROR templates → one sample each.** Three distinct error templates usually mean three causes; one template repeated 5000 times means one cause. Never read more than the samples until a template alone doesn't explain the question.

## 2. When did it start: the spike view

```bash
loglens spikes app.log
```

Buckets problems (ERROR/WARNING/anything matching "error|fail|exception") across time — by timestamp if the log has them, by line ranges if not. A flat line of warnings with one tall spike answers "when did it break" precisely, and the neighboring templates tell you what broke with it.

## 3. Follow-ups that actually help

- **Widen around the incident:** `loglens scan` gave the line range (`L902-L1050`); read ±20 lines around the first ERROR with normal tools *only now* — a bounded, purposeful read.
- **Compare periods:** run `scan` on a slice from before and after (`sed -n` a range into a temp file) and diff the template lists — new templates are the change.
- **Group by a field** the templates can't see: if all failures share `user_id=42`, that's a per-tenant bug, not a global one. Extract candidate fields with plain grep *after* clustering identified which lines matter.
- **Confirm the fix** by re-running `scan` on the post-deploy log: the incident template's count should drop to zero, and no new templates should appear.

## 4. Honest limits

- Clustering is textual: two different bugs with identical log lines merge into one template (split by host/service/user with grep before clustering if that's suspected), and one bug with two renderings splits into two.
- Multi-line stack traces become separate templates per frame pattern; the sample lines usually make the grouping obvious anyway.
- Binary logs (journald binary, Windows Event Log) need export to text first.
- Timestamps are taken from the log's own text; formats that parse are ISO, bracketed Apache-style, and bare `HH:MM:SS`. No timestamps → spikes bucket by line ranges.

## 5. Report

```text
volume:   3,000 lines / 222 KB, 09:00-10:39
incident: 1 template × 149 errors, "api.db timeout after 30s", started 09:30:02, ended 10:05
cause:    read lines 900-920: connection pool exhausted (pool_size=5, 6 concurrent workers)
next:     reproduce locally with pool_size=5; fix or raise with a comment
```

Counts with line ranges and one real quote — that's what a human needs to stop guessing.

## Scope

Run on logs the user owns or is authorized to read. Logs often contain user data — quote the minimum necessary in reports, and never paste whole payloads into shared channels.
