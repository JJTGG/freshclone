#!/usr/bin/env python3
"""Fetch README and package metadata files at the repository HEAD commit."""
from pathlib import Path
import subprocess
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "tests" / "samples" / "corpus.txt"
SAMPLES = CORPUS.parent
SOURCES = SAMPLES / "SOURCES.md"
README_NAMES = ("README.md", "readme.md", "Readme.md", "README.rst", "README")
METADATA_NAMES = ("package.json", "pyproject.toml", "setup.cfg")
DOC_NAMES = ("CONTRIBUTING.md", "DEVELOPMENT.md", "docs/development.md")


def get(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "freshclone-extractor"})
    with urlopen(request, timeout=30) as response:
        return response.read()


def run_git_ls_remote(owner: str, repo: str) -> str:
    result = subprocess.run(["git", "ls-remote", f"https://github.com/{owner}/{repo}", "HEAD"], check=True, capture_output=True, text=True, timeout=30)
    return result.stdout.split()[0]


def fetch_optional(owner: str, repo: str, commit: str, names: tuple[str, ...]) -> list[tuple[str, bytes]]:
    found = []
    for name in names:
        try:
            found.append((name, get(f"https://raw.githubusercontent.com/{owner}/{repo}/{commit}/{name}")))
        except HTTPError as error:
            if error.code != 404:
                raise
    return found


def fetch_readme(owner: str, repo: str, commit: str) -> tuple[bytes, str]:
    found = fetch_optional(owner, repo, commit, README_NAMES)
    if not found:
        raise FileNotFoundError("README file not found")
    name, content = found[0]
    return content, name


def corpus_entries() -> list[str]:
    return [line.strip() for line in CORPUS.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]


def main() -> None:
    fetched = []
    failures = []
    entries = corpus_entries()
    for entry in entries:
        owner, repo = entry.split("/", 1)
        try:
            commit = run_git_ls_remote(owner, repo)
            content, readme_name = fetch_readme(owner, repo, commit)
            extension = ".rst" if readme_name.endswith(".rst") else ".md"
            (SAMPLES / f"{owner}__{repo}{extension}").write_bytes(content)
            for name, metadata in fetch_optional(owner, repo, commit, METADATA_NAMES):
                (SAMPLES / f"{owner}__{repo}.{name}").write_bytes(metadata)
            for name, documentation in fetch_optional(owner, repo, commit, DOC_NAMES):
                output = SAMPLES / f"{owner}__{repo}__{name.replace('/', '__')}"
                output.write_bytes(documentation)
            fetched.append(f"- `{entry}` — `{commit}` — `{readme_name}`")
        except (HTTPError, URLError, OSError, TimeoutError, subprocess.SubprocessError, FileNotFoundError, IndexError) as error:
            failures.append(f"- `{entry}` — FAILED: {error}")

    SOURCES.write_text("# README sources\n\n" + "\n".join(fetched + failures) + "\n", encoding="utf-8")
    print(f"Fetched {len(fetched)} README files; {len(failures)} failures")
    if entries and len(fetched) / len(entries) < 0.8:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
