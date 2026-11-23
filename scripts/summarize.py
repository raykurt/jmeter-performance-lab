"""Summarizes JMeter .jtl (CSV) result files and compares runs.

Usage:
  python scripts/summarize.py --run "Before index=results/read-before.jtl,results/write-before.jtl" \
                              --run "After index=results/read-after.jtl,results/write-after.jtl" \
                              --gate "After index:Search person by email:p95:200"

A run can combine several .jtl files (comma separated), e.g. a read test and a write test.

The gate fails the build (exit code 1) when the metric is above the limit
(milliseconds for latencies, percent for error_pct).
"""
import argparse
import csv
import math
import os
import sys
from collections import defaultdict


def percentile(sorted_values, pct):
    """Nearest-rank percentile, the same idea JMeter uses in its summary tables."""
    if not sorted_values:
        return 0
    rank = max(1, math.ceil(pct / 100 * len(sorted_values)))
    return sorted_values[rank - 1]


def summarize(paths):
    samples = defaultdict(list)
    for path in paths:
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                samples[row["label"]].append(row)

    stats = {}
    for label, rows in samples.items():
        elapsed = sorted(int(r["elapsed"]) for r in rows)
        start = min(int(r["timeStamp"]) for r in rows)
        end = max(int(r["timeStamp"]) + int(r["elapsed"]) for r in rows)
        errors = sum(1 for r in rows if r["success"].lower() != "true")
        seconds = max((end - start) / 1000, 0.001)
        stats[label] = {
            "samples": len(rows),
            "avg": sum(elapsed) / len(elapsed),
            "median": percentile(elapsed, 50),
            "p90": percentile(elapsed, 90),
            "p95": percentile(elapsed, 95),
            "p99": percentile(elapsed, 99),
            "max": elapsed[-1],
            "throughput": len(rows) / seconds,
            "error_pct": 100 * errors / len(rows),
        }
    return stats


def to_markdown(results):
    lines = [
        "| Run | Request | Samples | Avg (ms) | Median | P90 | P95 | P99 | Max | Throughput (req/s) | Errors |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for run, stats in results.items():
        for label, s in sorted(stats.items()):
            lines.append(
                f"| {run} | {label} | {s['samples']} | {s['avg']:.0f} | {s['median']} | {s['p90']} | "
                f"{s['p95']} | {s['p99']} | {s['max']} | {s['throughput']:.1f} | {s['error_pct']:.1f}% |"
            )
    return "\n".join(lines)


def comparison(results):
    """P95 of the first run vs the last run for every request that appears in both."""
    runs = list(results)
    if len(runs) < 2:
        return ""
    first, last = results[runs[0]], results[runs[-1]]
    lines = [
        f"| Request | P95 {runs[0]} | P95 {runs[-1]} | Change |",
        "|---|---:|---:|---|",
    ]
    for label in sorted(set(first) & set(last)):
        before, after = first[label]["p95"], last[label]["p95"]
        if after < before:
            change = f"{before / max(after, 1):.0f}x faster"
        elif after > before:
            change = f"{(after - before) / max(before, 1) * 100:.0f}% slower"
        else:
            change = "no change"
        lines.append(f"| {label} | {before} ms | {after} ms | {change} |")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", required=True, help='"Name=path/to/results.jtl"')
    parser.add_argument("--gate", action="append", default=[], help='"Run:Request:metric:limit"')
    parser.add_argument("--title", default="JMeter results", help="heading of the report")
    args = parser.parse_args()

    results = {}
    for item in args.run:
        name, paths = item.split("=", 1)
        results[name] = summarize(paths.split(","))

    report = f"## {args.title}\n\n" + to_markdown(results) + "\n"
    compare = comparison(results)
    if compare:
        report += "\n### Before vs after\n\n" + compare + "\n"
    failures = []
    for gate in args.gate:
        run, label, metric, limit = gate.rsplit(":", 3)
        value = results.get(run, {}).get(label, {}).get(metric)
        unit = "%" if metric == "error_pct" else " ms"
        if value is None:
            failures.append(f"Gate '{gate}': no data")
        elif value > float(limit):
            failures.append(f"Gate failed: {run} / {label} {metric} = {value:g}{unit} (limit {limit}{unit})")
        else:
            report += f"\n✅ Gate passed: {run} / {label} {metric} = {value:g}{unit} (limit {limit}{unit})"

    for failure in failures:
        report += f"\n❌ {failure}"

    print(report)
    summary_file = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_file:
        with open(summary_file, "a", encoding="utf-8") as f:
            f.write(report + "\n")

    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    main()
