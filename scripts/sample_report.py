#!/usr/bin/env python3
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freshclone.extractor import extract

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "tests" / "samples"
SOURCES = SAMPLES / "SOURCES.md"


def source_counts() -> tuple[int, int]:
    fetched = 0
    failed = 0
    if SOURCES.exists():
        for line in SOURCES.read_text(encoding="utf-8").splitlines():
            if line.startswith("- ") and "FAILED" in line:
                failed += 1
            elif line.startswith("- "):
                fetched += 1
    return fetched, failed


def build_report() -> str:
    summary = ["# FreshClone extractor sample report", ""]
    fetched, failed = source_counts()
    unsupported = 0
    usable = 0
    skipped = 0
    no_setup = 0

    for readme in sorted(SAMPLES.glob("*__*.md")):
        blocks = extract(readme.read_text(encoding="utf-8-sig"))
        summary.append(f"## {readme.name}")
        if not blocks:
            no_setup += 1
            summary.append("- **No setup section found**")
        elif any(block.status == "usable" for block in blocks):
            usable += 1
        for block in blocks:
            if block.status == "usable":
                summary.append(f"- Usable, line {block.line}, heading **{block.heading}**: `{'; '.join(block.commands)}`")
            else:
                skipped += 1
                summary.append(f"- Skipped, line {block.line}, heading **{block.heading}**: {block.reason}")
        summary.append("")

    for readme in sorted(SAMPLES.glob("*__*.rst")):
        unsupported += 1
        summary.append(f"## {readme.name}\n- **Unsupported format**")

    summary.extend([
        "## Totals",
        f"- READMEs fetched: **{fetched}**",
        f"- Fetch failures: **{failed}**",
        f"- Unsupported formats: **{unsupported}**",
        f"- READMEs with at least one usable block: **{usable}**",
        f"- Skipped blocks: **{skipped}**",
        f"- No-setup READMEs: **{no_setup}**",
    ])
    return "\n".join(summary) + "\n"


def main() -> None:
    report = build_report()
    print(report)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(report)


if __name__ == "__main__":
    main()
