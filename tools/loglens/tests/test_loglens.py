import json

import pytest

from loglens.cli import main
from loglens.core import normalize, scan, severity_of, spikes


@pytest.fixture(scope="module")
def log_file(tmp_path_factory):
    d = tmp_path_factory.mktemp("log")
    path = d / "app.log"
    lines = []
    for i in range(1, 301):
        ts = f"2026-10-30 09:{i // 60:02d}:{i % 60:02d}"
        if i == 50:
            lines.append(f"{ts} ERROR db timeout query=select * from lots where id={i}")
        elif i == 120:
            lines.append(f"{ts} ERROR db timeout query=select * from lots where id=999")
        elif i % 10 == 0:
            lines.append(f"{ts} WARNING rate limit approach key=ip:{i % 5} count={i}")
        else:
            lines.append(f"{ts} INFO request handled path=/api/lots/{i} status=200 dur={i}ms")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def test_normalize_collapses_variables():
    line = "2026-10-30 09:00:01 ERROR id=9b2f5c1e-7a3d-4b8a-9c0d-1e2f3a4b5c6d ip=10.0.0.5 hash=0xDEADBEEF99 count=42 msg=\"boom\""
    n = normalize(line)
    assert "<uuid>" in n and "<ip>" in n and "<hex>" in n and '"…"' in n
    assert "42" not in n.replace("<n>", "").replace("<ip>", "")


def test_scan_clusters_same_template(log_file):
    r = scan(log_file)
    # 298 INFO lines differ only in digits/paths -> one template
    info = [t for t in r.templates if "INFO" in t.pattern]
    assert len(info) == 1 and info[0].count == 270
    assert r.templates and len(r.templates) <= 6


def test_scan_severity_counts(log_file):
    r = scan(log_file)
    assert r.severities["ERROR"] == 2
    assert r.severities["WARNING"] == 28  # i=50,120 became ERRORs
    assert r.counts()["ERROR"] == 2


def test_scan_timeframe_and_streaming_stats(log_file):
    r = scan(log_file)
    assert r.lines == 300
    assert r.timeframe.startswith("2026-10-30 09:00:01") and r.timeframe.endswith("09:05:00")


def test_spikes_finds_planted_cluster(log_file):
    data = spikes(log_file, buckets=10)
    assert data["total_problems"] >= 2
    worst = max(data["buckets"], key=lambda b: b["problems"])
    # the two ERROR lines sit at lines 50 and 120 — bucket 0-1 or 3-4 of 10
    assert worst["problems"] >= 1


def test_spikes_without_timestamps_buckets_by_lines(tmp_path):
    p = tmp_path / "plain.log"
    p.write_text("\n".join(f"ERR no timestamp {i}" for i in range(1, 101)) + "\n", encoding="utf-8")
    data = spikes(p, buckets=4)
    assert data["total_problems"] == 100
    assert all("lines" in b["label"] for b in data["buckets"])


def test_severity_variants():
    assert severity_of("2026-10-30 ERR x") == "ERROR"
    assert severity_of("crit: disk full") == "CRITICAL"
    assert severity_of("all fine") == ""


def test_cli_scan_text(log_file, capsys):
    assert main(["scan", log_file]) == 0
    out = capsys.readouterr().out
    assert "lines    300" in out and "ERROR 2" in out and "distinct templates" in out


def test_cli_scan_json(log_file, capsys):
    assert main(["scan", log_file, "--top", "3", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["lines"] == 300 and len(data["templates"]) <= 3


def test_cli_spikes_json(log_file, capsys):
    assert main(["spikes", log_file, "--buckets", "5", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["total_problems"] >= 2 and len(data["buckets"]) <= 5


def test_cli_demo(tmp_path, capsys):
    assert main(["demo", str(tmp_path / "d")]) == 0
    out = capsys.readouterr().out
    assert "planted incident" in out
    assert (tmp_path / "d" / "app.log").stat().st_size > 10000
