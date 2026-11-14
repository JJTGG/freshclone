#!/usr/bin/env python3
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freshclone.extractor import extract

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "tests" / "samples"
SOURCES = SAMPLES / "SOURCES.md"


def fetch_counts() -> tuple[int, int]:
    fetched = 0
    failures = 0
    if SOURCES.exists():
        for line in SOURCES.read_text(encoding="utf-8").splitlines():
            if line.startswith("- ") and "FAILED" in line:
                failures += 1
            elif line.startswith("- "):
                fetched += 1
    return fetched, failures


def main() -> None:
    summary = ["# FreshClone extractor sample report", ""]
    fetched, failures = fetch_counts()
    usable_readmes = 0
    skipped_blocks = 0
    no_setup = 0

    for readme in sorted(SAMPLES.glob("*.md")):
        blocks = extract(readme.read_text(encoding="utf-8-sig"))
        summary.append(f"## {readme.name}")
        if not blocks:
            no_setup += 1
            summary.append("- **No setup section found**")
            summary.append("")
            continue
        if any(block.status == "usable" for block in blocks):
            usable_readmes += 1
        for block in blocks:
            if block.status == "usable":
                summary.append(f"- Usable, line {block.line}, heading **{block.heading}**: `{'; '.join(block.commands)}`")
            else:
                skipped_blocks += 1
                summary.append(f"- Skipped, line {block.line}, heading **{block.heading}**: {block.reason}")
        summary.append("")

    summary.extend([
        "## Totals",
        f"- READMEs fetched: **{fetched}**",
        f"- Fetch failures: **{failures}**",
        f"- READMEs with at least one usable block: **{usable_readmes}**",
        f"- Skipped blocks: **{skipped_blocks}**",
        f"- No-setup READMEs: **{no_setup}**",
    ])
    report = "\n".join(summary) + "\n"
    print(report)
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if path:
        with Path(path).open("a", encoding="utf-8") as handle:
            handle.write(report)


if __name__ == "__main__":
    main()
