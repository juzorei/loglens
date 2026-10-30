"""loglens CLI: cluster a big log into templates, count severities, find spikes."""

from __future__ import annotations

import argparse
import json
import sys

from . import __version__
from .core import Scan, scan, spikes

BAR_WIDTH = 40


def bar(n: int, max_n: int) -> str:
    width = max(1, round(BAR_WIDTH * n / max_n)) if max_n else 1
    return "█" * width


def cmd_scan(args) -> int:
    result = scan(args.log)
    if args.json:
        print(json.dumps({
            "file": result.path, "lines": result.lines, "bytes": result.bytes_read,
            "timeframe": result.timeframe, "severities": result.counts(),
            "templates": [{"pattern": t.pattern, "count": t.count,
                           "lines": [t.first_line, t.last_line], "severity": t.severity,
                           "sample": t.sample}
                          for t in result.top(args.top)],
        }, indent=2))
        return 0
    print(f"file     {result.path}")
    print(f"lines    {result.lines:,} ({result.bytes_read:,} bytes)")
    if result.timeframe:
        print(f"time     {result.timeframe}")
    counts = result.counts()
    if counts:
        print("levels   " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))
    max_n = max((t.count for t in result.top(args.top)), default=1)
    for t in result.top(args.top):
        print(f"\n  {t.count:>7,}×  L{t.first_line}-L{t.last_line}"
              + (f"  [{t.severity}]" if t.severity else ""))
        print(f"        {t.sample[:160]}")
        print(f"        {bar(t.count, max_n)}")
    print(f"\n{len(result.templates)} distinct templates; showing top {min(args.top, len(result.templates))}")
    return 0


def cmd_spikes(args) -> int:
    data = spikes(args.log, buckets=args.buckets)
    if args.json:
        print(json.dumps(data, indent=2))
        return 0
    print(f"problems across {len(data['buckets'])} buckets "
          f"(total {data.get('total_problems', 0)} in {data.get('total_lines', 0):,} lines)")
    max_n = max((b["problems"] for b in data["buckets"]), default=1)
    for b in data["buckets"]:
        print(f"  {b['label']:<30} {b['problems']:>7,}  {bar(b['problems'], max_n)}")
    if not data["buckets"]:
        print("  (no errors, warnings or failures found)")
    return 0


def cmd_demo(args) -> int:
    from pathlib import Path
    d = Path(args.directory)
    d.mkdir(parents=True, exist_ok=True)
    log = d / "app.log"
    import datetime
    import random
    random.seed(42)
    base = datetime.datetime(2026, 10, 30, 9, 0, 0)
    lines = []
    for i in range(3000):
        ts = (base + datetime.timedelta(seconds=i * 2)).isoformat(sep=" ")
        roll = random.random()
        if 900 < i < 1050:  # planted incident spike
            lines.append(f"{ts} ERROR api.db timeout after 30s query=select * from lots where id={random.randint(1, 999)}")
        elif roll < 0.7:
            lines.append(f"{ts} INFO request handled path=/api/lots/{random.randint(1, 999)} status=200 dur={random.randint(2, 90)}ms")
        elif roll < 0.9:
            lines.append(f"{ts} DEBUG cache hit key=user:{random.randint(1, 99)} ttl={random.randint(10, 300)}")
        else:
            lines.append(f"{ts} WARN rate limit approach key=ip:{random.randint(1, 20)} count={random.randint(90, 100)}")
    log.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote synthetic log: {log} ({log.stat().st_size:,} bytes, 3000 lines, planted incident at lines ~900-1050)\n")
    print("try:")
    print(f"  loglens scan {log}")
    print(f"  loglens spikes {log}")
    print(f"  loglens scan {log} --json")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="loglens", description=__doc__)
    parser.add_argument("--version", action="version", version=f"loglens {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("scan", help="cluster a log into templates with counts and samples")
    p.add_argument("log")
    p.add_argument("--top", type=int, default=15)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser("spikes", help="show when problems happen (time buckets or line ranges)")
    p.add_argument("log")
    p.add_argument("--buckets", type=int, default=30)
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_spikes)

    p = sub.add_parser("demo", help="write a synthetic log with a planted incident")
    p.add_argument("directory", nargs="?", default="loglens-demo")
    p.set_defaults(func=cmd_demo)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except OSError as exc:
        print(f"loglens: error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
