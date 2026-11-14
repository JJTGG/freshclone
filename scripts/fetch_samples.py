#!/usr/bin/env python3
"""Fetch raw README files and record their resolved source commits."""
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import json

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "samples" / "corpus.txt"
SAMPLES = CORPUS.parent
SOURCES = SAMPLES / "SOURCES.md"


def get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "freshclone-extractor"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def fetch_readme(owner: str, repo: str, commit: str) -> tuple[bytes, str]:
    for name in ("README.md", "README.rst"):
        url = f"https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{name}"
        try:
            return get(url), name
        except HTTPError as error:
            if error.code != 404:
                raise
    raise FileNotFoundError("README.md or README.rst")


def main() -> None:
    entries = []
    failures = []
    for raw in CORPUS.read_text(encoding="utf-8").splitlines():
        entry = raw.strip()
        if not entry or entry.startswith("#"):
            continue
        owner, repo = entry.split("/", 1)
        try:
            metadata = json.loads(get(f"https://api.github.com/repos/{owner}/{repo}"))
            branch = metadata["default_branch"]
            commit_data = json.loads(get(f"https://api.github.com/repos/{owner}/{repo}/commits/{branch}"))
            commit = commit_data["sha"]
            content, readme_name = fetch_readme(owner, repo, commit)
            (SAMPLES / f"{owner}__{repo}.md").write_bytes(content)
            entries.append(f"- `{owner}/{repo}` — `{commit}` — `{readme_name}`")
        except (HTTPError, URLError, KeyError, ValueError, FileNotFoundError) as error:
            failures.append(f"- `{owner}/{repo}` — FAILED: {error}")

    SOURCES.write_text("# README sources\n\n" + "\n".join(entries + failures) + "\n", encoding="utf-8")
    print(f"Fetched {len(entries)} README files; {len(failures)} failures")


if __name__ == "__main__":
    main()
