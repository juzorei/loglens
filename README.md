# loglens

[English](README.md) | [Русский](README.ru.md)

[![CI](https://github.com/juzorei/loglens/actions/workflows/ci.yml/badge.svg)](https://github.com/juzorei/loglens/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/github/license/juzorei/loglens)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/logtriage)](https://pypi.org/project/logtriage/)

An agent skill and a CLI that diagnose what happened in a huge log without reading it line by line.

A 500 MB log cannot be read — not by a human, not by an agent with finite context. But logs are repetitive: normalize the variable parts and 3000 nearly-identical lines collapse into a handful of templates with counts, line ranges and one real sample each. `loglens` streams any text log (memory holds templates, not the file), clusters it, counts severities, and shows when problems spiked:

```text
$ loglens scan app.log
lines    3,000 (222,367 bytes)
time     2026-10-30 09:00:00 … 2026-10-30 10:39:58
levels   INFO 1,999, DEBUG 579, WARNING 273, ERROR 149

  149×  L902-L1050  [ERROR]
        2026-10-30 09:30:02 ERROR api.db timeout after 30s query=select * from lots where id=491
```

## What's in the repo

- **[skills/log-triage](skills/log-triage)** — the reading order for coding agents: severity counts → top error templates → one sample each → a bounded read around the incident. Compare periods, group by fields, confirm fixes by re-scanning.
- **tools/loglens** — the CLI ([README](tools/loglens/README.md)): `scan` (template clustering), `spikes` (time-bucket problem counts), `demo` (synthetic log with a planted incident). Streaming, `--json`, stdlib only.

## Install

```bash
pip install logtriage
npx skills add juzorei/loglens
```

## More from this portfolio

Part of a series of focused skill+CLI tools by the same author:

- [ci-autopsy](https://github.com/juzorei/ci-autopsy) — the triage family: failed CI runs instead of logs
- [flakehunt](https://github.com/juzorei/flakehunt) — is it in the logs because it's flaky?
- [hookbench](https://github.com/juzorei/hookbench) — integration failures find their way into logs too

Browse the rest at the [juzorei profile](https://github.com/juzorei?tab=repositories).

## Scope

Run on logs you own or are authorized to read. Logs often contain user data — quote the minimum necessary in reports.

MIT licensed.
