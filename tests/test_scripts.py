import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from scripts import fetch_samples, sample_report


class FetchSamplesTests(unittest.TestCase):
    def test_fetcher_uses_ls_remote_and_preserves_readme_extension(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.txt"
            samples = root / "samples"
            samples.mkdir()
            corpus.write_text("owner/repo\n", encoding="utf-8")
            def response(url):
                if url.endswith("/README.md") or url.endswith("/readme.md") or url.endswith("/Readme.md"):
                    raise HTTPError(url, 404, "missing", {}, None)
                return b"README.rst"
            with patch.object(fetch_samples, "CORPUS", corpus), patch.object(fetch_samples, "SAMPLES", samples), patch.object(fetch_samples, "SOURCES", samples / "SOURCES.md"), patch.object(fetch_samples, "run_git_ls_remote", return_value="abc123"), patch.object(fetch_samples, "get", side_effect=response):
                fetch_samples.main()
            self.assertTrue((samples / "owner__repo.rst").exists())
            self.assertIn("abc123", (samples / "SOURCES.md").read_text(encoding="utf-8"))

    def test_fetcher_saves_package_metadata_at_the_same_sha(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            corpus = root / "corpus.txt"
            samples = root / "samples"
            samples.mkdir()
            corpus.write_text("owner/repo\n", encoding="utf-8")
            calls = []
            def response(url):
                calls.append(url)
                if url.endswith("/README.md"):
                    return b"## Setup\n```bash\nnpm install repo\n```"
                if url.endswith(("/package.json", "/pyproject.toml", "/setup.cfg")):
                    return b"{\"name\": \"repo\"}" if url.endswith("package.json") else b""
                raise HTTPError(url, 404, "missing", {}, None)
            with patch.object(fetch_samples, "CORPUS", corpus), patch.object(fetch_samples, "SAMPLES", samples), patch.object(fetch_samples, "SOURCES", samples / "SOURCES.md"), patch.object(fetch_samples, "run_git_ls_remote", return_value="abc123"), patch.object(fetch_samples, "get", side_effect=response):
                fetch_samples.main()
            self.assertTrue((samples / "owner__repo.package.json").exists())
            self.assertIn("abc123", calls[0] if calls else "")


class SampleReportTests(unittest.TestCase):
    def test_report_excludes_sources_and_rst_from_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            samples = Path(directory)
            (samples / "owner__one.md").write_text("## Setup\n```bash\necho ok\n```\n", encoding="utf-8")
            (samples / "owner__two.rst").write_text("unsupported", encoding="utf-8")
            (samples / "SOURCES.md").write_text("sources", encoding="utf-8")
            with patch.object(sample_report, "SAMPLES", samples):
                report = sample_report.build_report()
            self.assertIn("READMEs fetched", report)
            self.assertIn("Unsupported format", report)
            self.assertNotIn("SOURCES.md", report)
            self.assertIn("usable", report)


if __name__ == "__main__":
    unittest.main()
