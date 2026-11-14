#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freshclone.extractor import extract

sample_dir = Path(__file__).parent / "samples"
summary = ["# FreshClone extractor sample report", ""]
usable_readmes = 0
skipped_blocks = 0
no_setup = 0

for readme in sorted(sample_dir.glob("*.md")):
    blocks = extract(readme.read_text(encoding="utf-8-sig"), repo_root=readme.parent)
    summary.append(f"## {readme.name}")
    if not blocks:
        no_setup += 1
        summary.append("- **No setup section found**")
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
    f"- READMEs with at least one usable block: **{usable_readmes}**",
    f"- Total skipped blocks: **{skipped_blocks}**",
    f"- READMEs with no setup section: **{no_setup}**",
])
report = "\n".join(summary) + "\n"
print(report)
if path := os.environ.get("GITHUB_STEP_SUMMARY"):
    Path(path).write_text(report, encoding="utf-8")
