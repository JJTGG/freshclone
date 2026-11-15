#!/usr/bin/env python3
import json
import os
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from freshclone.extractor import extract, find_headings, read_fences

ROOT = Path(__file__).resolve().parents[1]
SAMPLES = ROOT / "tests" / "samples"
SOURCES = SAMPLES / "SOURCES.md"
HIGH_PRIORITY = {"contributing", "development", "dev setup", "setup", "getting started", "quick start", "quickstart", "build"}
LOW_PRIORITY = {"install"}


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


def tier_for_heading(heading: str) -> str | None:
    normalized = heading.lower().strip()
    if normalized in HIGH_PRIORITY:
        return "HIGH"
    if normalized == "install":
        return "LOW"
    return None


def owner_for_sample(readme: Path) -> str:
    return readme.name.split("__", 1)[0]


def metadata_package_name(readme: Path) -> str | None:
    prefix = readme.with_suffix("")
    for suffix in (".package.json", ".pyproject.toml", ".setup.cfg"):
        path = Path(str(prefix) + suffix)
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8-sig")
        if suffix == ".package.json":
            try:
                return json.loads(text).get("name")
            except (ValueError, AttributeError):
                continue
        match = re.search(r"^name\s*=\s*[\"']([^\"']+)[\"']", text, re.M)
        if match:
            return match.group(1)
    return None


def build_report() -> str:
    summary = ["# FreshClone extractor sample report", ""]
    fetched, failed = source_counts()
    unsupported = 0
    skipped = 0
    no_setup = 0
    tier_totals = {"HIGH": {}, "LOW": {}}

    for readme in sorted(SAMPLES.glob("*__*.md")):
        text = readme.read_text(encoding="utf-8-sig")
        package_name = metadata_package_name(readme)
        blocks = extract(text, package_name=package_name)
        owner_group = "JJTGG/*" if owner_for_sample(readme) == "JJTGG" else "all others"
        summary.append(f"## {readme.name}")
        usable_blocks = [block for block in blocks if block.status == "usable"]
        if not usable_blocks:
            no_setup += 1
            headings = find_headings(text.splitlines())
            fences = read_fences(text.splitlines(), headings)
            heading_names = ", ".join(heading for _, heading, _ in headings) or "none"
            non_target = sum(1 for priority, *_ in fences if priority is None)
            summary.append(f"- **No usable setup block**. Headings found: {heading_names}; non-target fenced blocks: **{non_target}**")
        for block in blocks:
            tier = tier_for_heading(block.heading)
            if block.status == "usable":
                if tier:
                    stats = tier_totals[tier].setdefault(owner_group, [0, 0])
                    stats[0] += 1
                summary.append(f"- Usable, line {block.line}, heading **{block.heading}**: `{'; '.join(block.commands)}`")
            else:
                skipped += 1
                trigger = block.reason
                if block.commands:
                    trigger = f"{trigger}; command: `{'; '.join(block.commands)}`"
                summary.append(f"- Skipped, line {block.line}, heading **{block.heading}**: {block.reason}. Trigger: {trigger}")
        if blocks:
            for heading in {block.heading for block in blocks}:
                tier = tier_for_heading(heading)
                if tier:
                    stats = tier_totals[tier].setdefault(owner_group, [0, 0])
                    stats[1] += 1
        summary.append("")

    for readme in sorted(SAMPLES.glob("*__*.rst")):
        unsupported += 1
        summary.append(f"## {readme.name}\n- **Unsupported format**")

    summary.extend([
        "## Totals",
        f"- READMEs fetched: **{fetched}**",
        f"- Fetch failures: **{failed}**",
        f"- Unsupported formats: **{unsupported}**",
        f"- Skipped blocks: **{skipped}**",
        f"- No-setup READMEs: **{no_setup}**",
        "",
        "## Confidence tiers by corpus group",
    ])
    for tier in ("HIGH", "LOW"):
        summary.append(f"### {tier}")
        combined = [0, 0]
        for group in ("JJTGG/*", "all others"):
            usable_count, total_count = tier_totals[tier].get(group, [0, 0])
            combined[0] += usable_count
            combined[1] += total_count
            hit_rate = usable_count / total_count * 100 if total_count else 0.0
            summary.append(f"- {group}: **{usable_count}/{total_count} ({hit_rate:.1f}%)**")
        hit_rate = combined[0] / combined[1] * 100 if combined[1] else 0.0
        summary.append(f"- Combined: **{combined[0]}/{combined[1]} ({hit_rate:.1f}%)**")

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
