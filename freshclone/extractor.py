#!/usr/bin/env python3
"""Extract likely setup command blocks from a Markdown README."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

HIGH_PRIORITY = {
    "contributing": 0,
    "development": 1,
    "dev setup": 2,
    "setup": 3,
    "getting started": 4,
    "quick start": 5,
    "build": 6,
}
LOW_PRIORITY = {"install"}
LANGUAGES = {"", "bash", "sh", "shell", "console"}
PLACEHOLDER = re.compile(r"<[^>]+>|\bYOUR_[A-Z0-9_]+\b")
INTERACTIVE = re.compile(r"(^|\s)(read|select|passwd|ssh|vim|nano|top|htop|python\s+-i|node\s*$)(\s|$)", re.I)
ALTERNATIVE = re.compile(r"\b(or|alternatively)\b|\b(macOS|windows|brew|yarn|pnpm)\b", re.I)
PROMPT = re.compile(r"^\s*\$\s?")


@dataclass
class Block:
    status: str
    reason: str
    heading: str
    line: int
    commands: list[str]


def heading_key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def is_target_heading(text: str) -> bool:
    key = heading_key(text)
    return key in HIGH_PRIORITY or key in LOW_PRIORITY


def is_library_install(commands: list[str], package_name: str | None) -> bool:
    if not package_name:
        return False
    escaped = re.escape(package_name)
    return any(re.search(rf"\b(npm|pnpm|yarn)\s+install\s+.*{escaped}", command) for command in commands)


def clean_commands(lines: list[str]) -> list[str]:
    commands = []
    for line in lines:
        line = PROMPT.sub("", line).strip()
        if not line or line.startswith("#"):
            continue
        commands.append(line)
    return commands


def extract(text: str, package_name: str | None = None) -> list[Block]:
    lines = text.splitlines()
    candidates = []
    current_heading = ""
    current_priority = None
    in_fence = False
    fence_language = None
    fence_start = 0
    fence_lines: list[str] = []

    for number, raw in enumerate(lines, 1):
        heading = re.match(r"^#{1,6}\s+(.+?)\s*#*\s*$", raw)
        if heading and not in_fence:
            current_heading = heading.group(1)
            key = heading_key(current_heading)
            current_priority = HIGH_PRIORITY.get(key, 50 if key in LOW_PRIORITY else None)
            continue

        fence = re.match(r"^\s*```\s*([\w-]*)\s*$", raw)
        if fence:
            if not in_fence:
                in_fence = True
                fence_language = fence.group(1).lower()
                fence_start = number
                fence_lines = []
            else:
                if current_priority is not None and fence_language in LANGUAGES:
                    candidates.append((current_priority, fence_start, current_heading, fence_lines[:]))
                in_fence = False
                fence_language = None
            continue

        if in_fence:
            fence_lines.append(raw)

    candidates.sort(key=lambda item: (item[0], item[1]))
    has_high_priority = any(priority < 50 for priority, *_ in candidates)
    blocks: list[Block] = []
    for priority, line, heading, raw_lines in candidates:
        if priority == 50 and has_high_priority:
            continue
        commands = clean_commands(raw_lines)
        reason = None
        if not commands:
            reason = "empty or comment-only block"
        elif any(PLACEHOLDER.search(command) for command in commands):
            reason = "contains a placeholder or undocumented secret"
        elif any(INTERACTIVE.search(command) for command in commands):
            reason = "contains an interactive command"
        elif ALTERNATIVE.search(heading) or any(ALTERNATIVE.search(command) for command in commands):
            reason = "appears to be an alternative platform or package-manager block"
        elif is_library_install(commands, package_name):
            reason = "appears to install the project as a library consumer"
        if reason:
            blocks.append(Block("skipped", reason, heading, line, commands))
        else:
            blocks.append(Block("usable", "", heading, line, commands))
    return blocks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("readme", type=Path)
    parser.add_argument("--package-name")
    args = parser.parse_args()
    blocks = extract(args.readme.read_text(encoding="utf-8"), args.package_name)
    print(json.dumps([asdict(block) for block in blocks], indent=2))


if __name__ == "__main__":
    main()
