import json
import tempfile
import unittest
from pathlib import Path

from freshclone.extractor import extract


class ExtractorRegressionTests(unittest.TestCase):
    def test_info_string_is_accepted(self):
        blocks = extract('## Setup\n```bash title="x"\necho ok\n```')
        self.assertEqual(blocks[0].commands, ["echo ok"])

    def test_tilde_and_long_fences_match_their_closer(self):
        text = "## Setup\n~~~sh\necho tilde\n~~~\n\n## Build\n````bash\necho long\n```\necho still\n````"
        blocks = extract(text)
        self.assertEqual([b.commands for b in blocks], [["echo tilde"], ["echo long", "echo still"]])

    def test_html_comments_are_removed_before_parsing(self):
        text = "## Setup\n<!--\n```bash\necho hidden\n```\n-->\n```bash\necho visible\n```"
        blocks = extract(text)
        self.assertEqual([b.commands for b in blocks], [["echo visible"]])

    def test_bom_does_not_hide_first_heading(self):
        blocks = extract("\ufeff## Setup\n```bash\necho ok\n```")
        self.assertEqual(len(blocks), 1)

    def test_output_preserves_readme_order(self):
        text = "## Build\n```bash\necho build\n```\n## Development\n```bash\necho dev\n```"
        blocks = extract(text)
        self.assertEqual([b.commands[0] for b in blocks], ["echo build", "echo dev"])

    def test_subheading_inherits_parent_priority(self):
        text = "## Local development\n### Commands\n```bash\necho dev\n```"
        blocks = extract(text)
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0].heading, "Commands")

    def test_heading_matching_uses_contains_or_startswith(self):
        text = "## Installation\n```bash\necho install\n```\n## Quickstart guide\n```bash\necho quick\n```\n## Usage\n```bash\necho ignored\n```"
        blocks = extract(text)
        self.assertEqual([b.commands[0] for b in blocks], ["echo install", "echo quick"])

    def test_backslash_continuation_is_joined(self):
        blocks = extract("## Setup\n```bash\necho one \\\n  two\n```")
        self.assertEqual(blocks[0].commands, ["echo one two"])

    def test_console_keeps_only_prompts(self):
        text = "## Setup\n```console\n$ echo ok\nok\n$ echo again\nagain\n```"
        blocks = extract(text)
        self.assertEqual(blocks[0].commands, ["echo ok", "echo again"])

    def test_unsupported_language_is_reported(self):
        blocks = extract("## Setup\n```zsh\necho no\n```")
        self.assertEqual(blocks[0].status, "skipped")
        self.assertIn("unsupported", blocks[0].reason)

    def test_install_is_reported_when_higher_priority_exists(self):
        text = "## Development\n```bash\necho dev\n```\n## Install\n```bash\necho install\n```"
        blocks = extract(text)
        self.assertEqual(len(blocks), 2)
        self.assertIn("lower-priority", blocks[1].reason)

    def test_no_setup_section_is_explicit(self):
        self.assertEqual(extract("# Project\nNo commands here."), [])

    def test_placeholder_block_is_skipped(self):
        blocks = extract("## Setup\n```bash\nexport API_KEY=<your-key>\n```")
        self.assertEqual(blocks[0].status, "skipped")

    def test_alternative_prose_is_skipped(self):
        text = "## Setup\nUse this on Linux. Alternatively, use the macOS instructions.\n```bash\nbrew install tool\n```"
        blocks = extract(text)
        self.assertIn("alternative", blocks[0].reason)

    def test_project_library_install_is_skipped(self):
        blocks = extract("## Setup\n```bash\nnpm install freshclone\n```")
        self.assertEqual(blocks[0].status, "skipped")
        self.assertIn("library", blocks[0].reason)

    def test_own_clone_is_skipped_and_cd_is_rewritten(self):
        text = "## Setup\n```bash\ngit clone https://github.com/acme/demo.git\ncd demo\nnpm install\n```"
        blocks = extract(text, repo_url="https://github.com/acme/demo")
        self.assertIn("clone", blocks[0].reason)
        self.assertEqual(blocks[0].commands, ["cd /workspace/repo", "npm install"])

    def test_unsupported_host_commands_are_skipped(self):
        blocks = extract("## Setup\n```bash\nsudo apt-get update\n```")
        self.assertIn("not supported", blocks[0].reason)

    def test_yarn_install_is_not_an_alternative_by_itself(self):
        blocks = extract("## Setup\n```bash\nyarn install\n```")
        self.assertEqual(blocks[0].status, "usable")

    def test_interactive_detection_reports_the_command(self):
        blocks = extract("## Setup\n```bash\ncd top\n npm login\n```")
        self.assertIn("npm login", blocks[0].reason)

    def test_library_install_override_is_supported(self):
        blocks = extract("## Setup\n```bash\npip install demo\n```", package_name="demo")
        self.assertEqual(blocks[0].status, "skipped")


if __name__ == "__main__":
    unittest.main()
