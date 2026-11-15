#!/usr/bin/env python3
"""Extract likely setup commands from a Markdown README."""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

HIGH_PRIORITY = ("contributing", "development", "dev setup", "setup", "getting started", "quick start", "quickstart", "build")
LOW_PRIORITY = "install"
LANGUAGES = {"", "bash", "sh", "shell", "console"}
PLACEHOLDER = re.compile(r"<[^>]+>|\bYOUR_[A-Z0-9_]+\b|(?<!\$)\{[^}]+\}")
PROMPT = re.compile(r"^\s*\$\s?")
FIRST_WORD_INTERACTIVE = re.compile(r"^(read|select|passwd|ssh|vim|nano|top|htop|python\s+-i|node|npm\s+(init|login)|gh\s+auth\s+login)(?:\s|$)", re.I)
HOST_COMMAND = re.compile(r"^(sudo|apt|apt-get|dnf|brew|docker)(?:\s|$)|^docker\s+compose(?:\s|$)", re.I)
LIBRARY_INSTALL = re.compile(r"^(npm|pnpm|yarn)\s+(install|i|add)(?:\s|$)|^(pip|pip3)\s+install(?:\s|$)", re.I)


@dataclass
class Block:
    status: str
    reason: str
    heading: str
    line: int
    commands: list[str]


def heading_key(text: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", text.lower()).strip()


def priority_for(text: str) -> int | None:
    key = heading_key(text)
    if key.startswith(LOW_PRIORITY):
        return 50
    for priority, name in enumerate(HIGH_PRIORITY):
        if key.startswith(name) or name in key:
            return priority
    return None


def remove_comments(text: str) -> str:
    return re.sub(r"<!--.*?-->", "", text, flags=re.S)


def find_headings(lines: list[str]) -> list[tuple[int, str, int | None]]:
    headings = []
    stack: list[tuple[int, int | None]] = []
    for number, raw in enumerate(lines, 1):
        match = re.match(r"^(#{1,6})\s+(.+?)\s*#*\s*$", raw)
        if not match:
            continue
        level, title = len(match.group(1)), match.group(2)
        while stack and stack[-1][0] >= level:
            stack.pop()
        priority = priority_for(title)
        if heading_key(title).startswith("usage"):
            priority = None
        elif priority is None and stack:
            priority = stack[-1][1]
        stack.append((level, priority))
        headings.append((number, title, priority))
    return headings


def read_fences(lines: list[str], headings: list[tuple[int, str, int | None]]) -> list[tuple[int, str, int, list[str], str, str]]:
    result = []
    heading_index = 0
    active_heading = ""
    active_priority = None
    previous_end = None
    index = 0
    while index < len(lines):
        number = index + 1
        while heading_index < len(headings) and headings[heading_index][0] <= number:
            _, active_heading, active_priority = headings[heading_index]
            heading_index += 1
        match = re.match(r"^\s*(`{3,}|~{3,})(.*)$", lines[index])
        if not match:
            index += 1
            continue
        marker, info = match.groups()
        language = info.strip().split(None, 1)[0].lower() if info.strip() else ""
        start = number
        prose_start = previous_end if previous_end is not None else (headings[heading_index - 1][0] if headings else 1)
        prose = "\n".join(lines[prose_start:start - 1])
        body = []
        index += 1
        while index < len(lines):
            close = re.match(r"^\s*(`{3,}|~{3,})\s*$", lines[index])
            if close and close.group(1)[0] == marker[0] and len(close.group(1)) >= len(marker):
                break
            body.append(lines[index])
            index += 1
        end = index + 1
        if active_priority is not None:
            result.append((active_priority, active_heading, start, body, language, prose))
        previous_end = end
        index += 1
    return result


def join_continuations(lines: list[str]) -> list[str]:
    joined = []
    for line in lines:
        line = line.rstrip()
        if joined and joined[-1].endswith("\\"):
            joined[-1] = joined[-1][:-1].rstrip() + " " + line.strip()
        else:
            joined.append(line)
    return joined


def clean_commands(lines: list[str], language: str) -> list[str]:
    commands = []
    for raw in join_continuations(lines):
        if language == "console" and not raw.lstrip().startswith("$"):
            continue
        line = PROMPT.sub("", raw).strip()
        if line and not line.startswith("#"):
            commands.append(line)
    return commands


def package_name_from_files(repo_root: Path | None) -> str | None:
    if not repo_root:
        return None
    package = repo_root / "package.json"
    if package.exists():
        try:
            return json.loads(package.read_text(encoding="utf-8-sig")).get("name")
        except (OSError, ValueError):
            pass
    pyproject = repo_root / "pyproject.toml"
    if pyproject.exists():
        match = re.search(r"^name\s*=\s*[\"']([^\"']+)[\"']", pyproject.read_text(encoding="utf-8-sig"), re.M)
        if match:
            return match.group(1)
    return None


def normalize_prose(text: str) -> str:
    text = re.sub(r"[*_`~]", "", text.lower())
    return re.sub(r"[^a-z0-9:]+", " ", text).strip()


def is_alternative_prose(text: str) -> bool:
    normalized = normalize_prose(text)
    for line in normalized.splitlines():
        words = line.strip().split()
        if words and words[0].rstrip(":.,!?;-") in {"or", "alternatively", "otherwise"}:
            return True
    if re.search(r"(?:^|\s)(or|alternatively|otherwise)(?:\s|:|$)", normalized):
        return True
    return bool(re.search(r"(?:^|\s)(using|with|on)\s+[^:]+:", normalized))


def classify(commands: list[str], prose: str, package_name: str | None, repo_url: str | None) -> tuple[str, str, list[str]]:
    if not commands:
        return "skipped", "empty or comment-only block", commands
    if is_alternative_prose(prose):
        return "skipped", "alternative instructions", commands
    for command in commands:
        if PLACEHOLDER.search(command):
            return "skipped", f"contains a placeholder: {command}", commands
        if FIRST_WORD_INTERACTIVE.match(command):
            return "skipped", f"interactive command: {command}", commands
        if HOST_COMMAND.match(command):
            return "skipped", f"not supported in the non-root container: {command}", commands
    own_clone = next((command for command in commands if command.startswith("git clone") and repo_url and repo_url in command), None)
    if own_clone:
        rewritten = []
        cloned = False
        for command in commands:
            if command == own_clone:
                cloned = True
                continue
            if cloned and command.startswith("cd "):
                rewritten.append("cd /workspace/repo")
            else:
                rewritten.append(command)
        return "skipped", f"skipped own-repository clone: {own_clone}", rewritten
    if package_name:
        for command in commands:
            if LIBRARY_INSTALL.match(command) and re.search(rf"\b{re.escape(package_name)}\b", command):
                return "skipped", f"library consumer install: {command}", commands
    return "usable", "", commands


def extract(text: str, package_name: str | None = None, repo_root: Path | None = None, repo_url: str | None = None) -> list[Block]:
    lines = remove_comments(text).lstrip("\ufeff").splitlines()
    headings = find_headings(lines)
    fences = read_fences(lines, headings)
    high_exists = any(priority < 50 for priority, *_ in fences)
    blocks = []
    package_name = package_name or package_name_from_files(repo_root)
    for priority, heading, line, raw_lines, language, prose in fences:
        if language not in LANGUAGES:
            blocks.append(Block("skipped", f"unsupported language: {language}", heading, line, []))
            continue
        commands = clean_commands(raw_lines, language)
        if priority == 50 and high_exists:
            blocks.append(Block("skipped", "lower-priority install section ignored because a higher-priority section exists", heading, line, commands))
            continue
        status, reason, commands = classify(commands, prose, package_name, repo_url)
        blocks.append(Block(status, reason, heading, line, commands))
    return blocks


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("readme", type=Path)
    parser.add_argument("--package-name")
    parser.add_argument("--repo-url")
    args = parser.parse_args()

    text = args.readme.read_text(encoding="utf-8-sig")
    blocks = extract(text, args.package_name, args.readme.parent, args.repo_url)
    if not blocks:
        print("no setup section found")
        return

    print(json.dumps([asdict(block) for block in blocks], indent=2))


if __name__ == "__main__":
    main()
