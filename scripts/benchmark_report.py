#!/usr/bin/env python3
"""Benchmark report generator for altex + verapdf.

Runs verapdf PDF/UA-1 validation on original, tagged, and tagged+encoded
PDFs, then produces a structured comparison report.

Usage:
    python3 scripts/benchmark_report.py [--tag-first] [--output-json PATH]

With --tag-first, runs altex on all test PDFs before validating.
Without it, expects tagged PDFs to already exist in demos/output/.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BENCHMARKS_DIR = ROOT / "benchmarks"
OUTPUT_DIR = ROOT / "demos" / "output"

# Benchmark corpus: (tex_path, pdf_path) pairs relative to ROOT.
# All documents live under benchmarks/ — .edu-sourced, diverse CS topics.
BENCHMARK_PAIRS = [
    # Papers and lecture notes
    ("benchmarks/paper/wm-thesis.tex", "benchmarks/paper/wm-thesis.pdf"),
    ("benchmarks/paper/cambridge-dist-sys.tex", "benchmarks/paper/cambridge-dist-sys.pdf"),
    ("benchmarks/paper/elegantpaper-en.tex", "benchmarks/paper/elegantpaper-en.pdf"),
    # Beamer presentations
    ("benchmarks/beamer/tufts-beamer.tex", "benchmarks/beamer/tufts-beamer.pdf"),
    ("benchmarks/beamer/stanford-beamer.tex", "benchmarks/beamer/stanford-beamer.pdf"),
    ("benchmarks/beamer/ucdavis-beamer.tex", "benchmarks/beamer/ucdavis-beamer.pdf"),
    ("benchmarks/beamer/metropolis-demo.tex", "benchmarks/beamer/metropolis-demo.pdf"),
    # CV, syllabus, exam
    ("benchmarks/cv/duke-cv.tex", "benchmarks/cv/duke-cv.pdf"),
    ("benchmarks/syllabus/utoledo-math2850.tex", "benchmarks/syllabus/utoledo-math2850.pdf"),
    ("benchmarks/exam/duke-exam.tex", "benchmarks/exam/duke-exam.pdf"),
    # Homework assignments (probability, numerical methods, ML, combinatorics, HPC)
    ("benchmarks/homework/bu-cs237-hw.tex", "benchmarks/homework/bu-cs237-hw.pdf"),
    ("benchmarks/homework/uw-amath586-hw.tex", "benchmarks/homework/uw-amath586-hw.pdf"),
    ("benchmarks/homework/ucsd-math184a-hw.tex", "benchmarks/homework/ucsd-math184a-hw.pdf"),
    ("benchmarks/homework/ucsd-math184a-hw5.tex", "benchmarks/homework/ucsd-math184a-hw5.pdf"),
    ("benchmarks/homework/upenn-cs446-hw.tex", "benchmarks/homework/upenn-cs446-hw.pdf"),
    ("benchmarks/homework/jdavis-hw-template.tex", "benchmarks/homework/jdavis-hw-template.pdf"),
    ("benchmarks/homework/sfsu-csc746-hw.tex", "benchmarks/homework/sfsu-csc746-hw.pdf"),
]


@dataclass
class RuleResult:
    clause: str
    test_number: int
    description: str
    status: str  # "passed" or "failed"
    failed_checks: int
    tags: list[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    pdf_path: str
    passed_rules: int = 0
    failed_rules: int = 0
    passed_checks: int = 0
    failed_checks: int = 0
    failed_rule_details: list[RuleResult] = field(default_factory=list)
    error: str | None = None


@dataclass
class DocumentBenchmark:
    name: str
    tex_path: str
    original: ValidationResult | None = None
    tagged: ValidationResult | None = None
    tagged_encoded: ValidationResult | None = None


def run_verapdf(pdf_path: Path) -> ValidationResult:
    """Run verapdf -f ua1 on a PDF and parse JSON output."""
    if not pdf_path.exists():
        return ValidationResult(pdf_path=str(pdf_path), error=f"File not found: {pdf_path}")

    try:
        result = subprocess.run(
            ["verapdf", "-f", "ua1", "--format", "json", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError:
        return ValidationResult(pdf_path=str(pdf_path), error="verapdf not found in PATH")
    except subprocess.TimeoutExpired:
        return ValidationResult(pdf_path=str(pdf_path), error="verapdf timed out after 120s")

    try:
        data = json.loads(result.stdout)
        job = data["report"]["jobs"][0]
        vr = job["validationResult"][0]["details"]

        failed_details = []
        for rs in vr.get("ruleSummaries", []):
            if rs["ruleStatus"] == "FAILED":
                failed_details.append(RuleResult(
                    clause=rs["clause"],
                    test_number=rs["testNumber"],
                    description=rs["description"],
                    status="failed",
                    failed_checks=rs["failedChecks"],
                    tags=rs.get("tags", []),
                ))

        return ValidationResult(
            pdf_path=str(pdf_path),
            passed_rules=vr["passedRules"],
            failed_rules=vr["failedRules"],
            passed_checks=vr["passedChecks"],
            failed_checks=vr["failedChecks"],
            failed_rule_details=failed_details,
        )
    except (json.JSONDecodeError, KeyError, IndexError) as e:
        return ValidationResult(pdf_path=str(pdf_path), error=f"Parse error: {e}")


def run_altex(tex_path: Path, pdf_path: Path, output: Path, fix_encoding: bool = True) -> bool:
    """Run altex pipeline on a single document."""
    cmd = [sys.executable, "-m", "altex", str(tex_path), str(pdf_path), "-o", str(output)]
    if not fix_encoding:
        cmd.append("--no-fix-encoding")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=str(ROOT))
        if result.returncode != 0:
            print(f"  ALTEX ERROR: {result.stderr.strip()}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"  ALTEX ERROR: {e}", file=sys.stderr)
        return False


def run_benchmarks(tag_first: bool = False) -> list[DocumentBenchmark]:
    """Run full benchmark suite."""
    return _run_pairs(BENCHMARK_PAIRS, tag_first)


def _run_pairs(pairs: list[tuple[str, str]], tag_first: bool) -> list[DocumentBenchmark]:
    """Run benchmarks for a list of (tex, pdf) pairs."""
    results = []

    if tag_first:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for tex_rel, pdf_rel in pairs:
        tex_path = ROOT / tex_rel
        pdf_path = ROOT / pdf_rel
        name = pdf_path.stem

        if not pdf_path.exists():
            print(f"  SKIP {name} (no PDF)")
            continue

        print(f"  {name}...", end=" ", flush=True)

        bench = DocumentBenchmark(name=name, tex_path=tex_rel)

        # Validate original PDF
        bench.original = run_verapdf(pdf_path)

        # Tag if requested
        tagged_path = OUTPUT_DIR / f"{name}_tagged.pdf"
        encoded_path = OUTPUT_DIR / f"{name}_tagged_encoded.pdf"

        if tag_first:
            # "tagged" = without Ghostscript encoding fix.
            run_altex(tex_path, pdf_path, tagged_path, fix_encoding=False)
            # "encoded" = with Ghostscript (now the default).
            if _has_gs():
                run_altex(tex_path, pdf_path, encoded_path, fix_encoding=True)

        # Validate tagged versions
        if tagged_path.exists():
            bench.tagged = run_verapdf(tagged_path)
        if encoded_path.exists():
            bench.tagged_encoded = run_verapdf(encoded_path)

        print("done")
        results.append(bench)

    return results


def _has_gs() -> bool:
    try:
        subprocess.run(["gs", "--version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def format_report(benchmarks: list[DocumentBenchmark]) -> str:
    """Generate a human-readable benchmark report."""
    lines: list[str] = []
    lines.append("=" * 72)
    lines.append("  altex PDF/UA-1 Benchmark Report (verapdf)")
    lines.append("=" * 72)
    lines.append("")

    # Summary table
    lines.append("SUMMARY")
    lines.append("-" * 72)
    lines.append(f"{'Document':<25} {'Original':>12} {'Tagged':>12} {'Encoded':>12}")
    lines.append(f"{'':25} {'fail/total':>12} {'fail/total':>12} {'fail/total':>12}")
    lines.append("-" * 72)

    total_orig_fail = total_orig_check = 0
    total_tag_fail = total_tag_check = 0
    total_enc_fail = total_enc_check = 0

    for b in benchmarks:
        orig = _fmt_ratio(b.original)
        tag = _fmt_ratio(b.tagged)
        enc = _fmt_ratio(b.tagged_encoded)
        lines.append(f"  {b.name:<23} {orig:>12} {tag:>12} {enc:>12}")

        if b.original and not b.original.error:
            total_orig_fail += b.original.failed_checks
            total_orig_check += b.original.passed_checks + b.original.failed_checks
        if b.tagged and not b.tagged.error:
            total_tag_fail += b.tagged.failed_checks
            total_tag_check += b.tagged.passed_checks + b.tagged.failed_checks
        if b.tagged_encoded and not b.tagged_encoded.error:
            total_enc_fail += b.tagged_encoded.failed_checks
            total_enc_check += b.tagged_encoded.passed_checks + b.tagged_encoded.failed_checks

    lines.append("-" * 72)
    lines.append(f"  {'TOTAL':<23} {total_orig_fail}/{total_orig_check:>5}      "
                 f"{total_tag_fail}/{total_tag_check:>5}      "
                 f"{total_enc_fail}/{total_enc_check:>5}")
    lines.append("")

    # Rules fixed by altex
    lines.append("RULES FIXED BY ALTEX")
    lines.append("-" * 72)
    fixed, remaining = _compute_rule_deltas(benchmarks)
    for clause, desc in sorted(fixed.items()):
        lines.append(f"  ✅ [{clause}] {desc}")
    lines.append("")

    # Remaining failures
    lines.append("REMAINING FAILURES (post-tagging)")
    lines.append("-" * 72)
    for clause, (desc, counts) in sorted(remaining.items()):
        total_fc = sum(counts.values())
        docs = ", ".join(f"{n}({c})" for n, c in counts.items())
        lines.append(f"  ❌ [{clause}] {desc}")
        lines.append(f"     {total_fc} total failures across: {docs}")
    lines.append("")

    # Per-document detail
    lines.append("PER-DOCUMENT DETAILS")
    lines.append("-" * 72)
    for b in benchmarks:
        lines.append(f"\n  {b.name}")
        lines.append(f"  {'─' * 40}")

        for label, vr in [("Original", b.original), ("Tagged", b.tagged), ("Encoded", b.tagged_encoded)]:
            if vr is None:
                continue
            if vr.error:
                lines.append(f"    {label}: ERROR — {vr.error}")
                continue
            lines.append(f"    {label}: {vr.passed_rules} passed, {vr.failed_rules} failed "
                         f"({vr.failed_checks} check failures)")
            for rd in vr.failed_rule_details:
                lines.append(f"      [{rd.clause}:{rd.test_number}] ×{rd.failed_checks} — {rd.description[:60]}")

    lines.append("")
    return "\n".join(lines)


def _fmt_ratio(vr: ValidationResult | None) -> str:
    if vr is None:
        return "—"
    if vr.error:
        return "ERR"
    total = vr.passed_checks + vr.failed_checks
    return f"{vr.failed_checks}/{total}"


def _compute_rule_deltas(benchmarks: list[DocumentBenchmark]) -> tuple[dict, dict]:
    """Compute which rules altex fixes and which remain."""
    orig_rules: dict[str, str] = {}  # clause → description
    post_rules: dict[str, tuple[str, dict[str, int]]] = {}  # clause → (desc, {doc: count})

    for b in benchmarks:
        if b.original and not b.original.error:
            for rd in b.original.failed_rule_details:
                key = f"{rd.clause}:{rd.test_number}"
                orig_rules[key] = rd.description

        # Use encoded if available, else tagged
        post = b.tagged_encoded or b.tagged
        if post and not post.error:
            for rd in post.failed_rule_details:
                key = f"{rd.clause}:{rd.test_number}"
                if key not in post_rules:
                    post_rules[key] = (rd.description, {})
                post_rules[key][1][b.name] = rd.failed_checks

    fixed = {}
    for key, desc in orig_rules.items():
        if key not in post_rules:
            fixed[key] = desc

    return fixed, post_rules


def main():
    parser = argparse.ArgumentParser(description="altex PDF/UA benchmark suite")
    parser.add_argument("--tag-first", action="store_true",
                        help="Run altex pipeline before validating (regenerates tagged PDFs)")
    parser.add_argument("--output-json", type=Path,
                        help="Write raw results as JSON to this path")
    args = parser.parse_args()

    # Check verapdf
    try:
        subprocess.run(["verapdf", "--version"], capture_output=True, timeout=10)
    except FileNotFoundError:
        print("ERROR: verapdf not found in PATH. Install from https://verapdf.org/software/", file=sys.stderr)
        sys.exit(1)

    print("Running PDF/UA-1 benchmarks...\n")
    benchmarks = run_benchmarks(tag_first=args.tag_first)

    if not benchmarks:
        print("No test PDFs found. Ensure benchmarks/ directory exists.", file=sys.stderr)
        sys.exit(1)

    # Print report
    report = format_report(benchmarks)
    print()
    print(report)

    # Write JSON if requested
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output_json, "w") as f:
            json.dump([asdict(b) for b in benchmarks], f, indent=2)
        print(f"JSON results written to {args.output_json}")


if __name__ == "__main__":
    main()
