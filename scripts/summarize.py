"""Summarizes JMeter .jtl (CSV) result files and compares runs.

Usage:
  python scripts/summarize.py --run "Before index=results/before.jtl" \
                              --run "After index=results/after.jtl" \
                              --gate "After index:Search person by email:p95:200"

The gate fails the build (exit code 1) when the metric is above the limit in milliseconds.
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


def summarize(path):
    samples = defaultdict(list)
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", action="append", required=True, help='"Name=path/to/results.jtl"')
    parser.add_argument("--gate", action="append", default=[], help='"Run:Request:metric:max_ms"')
    args = parser.parse_args()

    results = {}
    for item in args.run:
        name, path = item.split("=", 1)
        results[name] = summarize(path)

    report = "## JMeter results\n\n" + to_markdown(results) + "\n"
    failures = []
    for gate in args.gate:
        run, label, metric, limit = gate.rsplit(":", 3)
        value = results.get(run, {}).get(label, {}).get(metric)
        if value is None:
            failures.append(f"Gate '{gate}': no data")
        elif value > float(limit):
            failures.append(f"Gate failed: {run} / {label} {metric} = {value} ms (limit {limit} ms)")
        else:
            report += f"\n✅ Gate passed: {run} / {label} {metric} = {value} ms (limit {limit} ms)"

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
