# loglens

Cluster big logs into templates with counts, severities and incident spikes — streaming, stdlib only, no file size limit.

```text
$ loglens scan app.log
lines    3,000 (222,367 bytes)
time     2026-10-30 09:00:00 … 2026-10-30 10:39:58
levels   INFO 1,999, DEBUG 579, WARNING 273, ERROR 149

  1,999×  L1-L2999  [INFO]
        2026-10-30 09:00:00 INFO request handled path=/api/lots/26 status=200 dur=37ms

  149×  L902-L1050  [ERROR]
        2026-10-30 09:30:02 ERROR api.db timeout after 30s query=select * from lots where id=491

$ loglens spikes app.log
problems across 30 buckets (total 422 in 3,000 lines)
  2026-10-30 09:33:26        149  ████████████████████████████████████████
```

A 500 MB log cannot be read — by a human or by an agent with finite context. But logs are repetitive: numbers, UUIDs, IPs, hashes and quoted strings normalize away, and 3000 nearly-identical lines collapse into a handful of templates with counts, line ranges and one real sample each. That's all the information a triage needs.

## Commands

```text
loglens scan <log> [--top 15] [--json]   # template clustering + severity counts
loglens spikes <log> [--buckets 30] [--json]  # when problems happen (time or line buckets)
loglens demo [dir]                       # synthetic log with a planted incident
```

Streaming: the file is read line by line, memory holds only templates. Any text log; timestamps understood in ISO, Apache-bracketed and bare `HH:MM:SS` forms (no timestamps → line-range buckets). Python 3.11+, stdlib only.

Install: `pip install loglens-cli` — or from this repo:
`pip install "git+https://github.com/juzorei/loglens#subdirectory=tools/loglens"`

The companion agent skill lives in [skills/log-triage](../skills/log-triage): cluster first, read only samples, then bounded reads around the incident. Skills: `npx skills add juzorei/loglens`.
