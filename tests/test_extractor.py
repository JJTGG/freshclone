import unittest

from freshclone.extractor import extract


class ExtractorRegressionTests(unittest.TestCase):
    def test_info_string_is_accepted(self):
        blocks = extract('## Setup\n```bash title="x"\necho ok\n```')
        self.assertEqual(blocks[0].commands, ["echo ok"])

    def test_tilde_and_long_fences_match_their_closer(self):
        text = "## Setup\n~~~sh\necho tilde\n~~~\n\n## Build\n````bash\necho long\necho still\n````"
        blocks = extract(text)
        self.assertEqual([b.commands for b in blocks], [["echo tilde"], ["echo long", "echo still"]])

    def test_short_or_different_fence_does_not_close_long_fence(self):
        text = "## Setup\n````bash\necho long\n```\n~~~\nstill\n````"
        blocks = extract(text)
        self.assertEqual(blocks[0].commands, ["echo long", "```", "~~~", "still"])

    def test_html_comments_are_removed_before_parsing(self):
        text = "## Setup\n<!--\n```bash\necho hidden\n```\n-->\n```bash\necho visible\n```"
        blocks = extract(text)
        self.assertEqual([b.commands for b in blocks], [["echo visible"]])

    def test_bom_does_not_hide_first_heading(self):
        self.assertEqual(len(extract("\ufeff## Setup\n```bash\necho ok\n```")), 1)

    def test_output_preserves_readme_order(self):
        text = "## Build\n```bash\necho build\n```\n## Development\n```bash\necho dev\n```"
        self.assertEqual([b.commands[0] for b in extract(text)], ["echo build", "echo dev"])

    def test_subheading_inherits_parent_priority(self):
        blocks = extract("## Local development\n### Commands\n```bash\necho dev\n```")
        self.assertEqual(blocks[0].heading, "Commands")

    def test_heading_matching_uses_contains_or_startswith(self):
        text = "## Installation\n```bash\necho install\n```\n## Quickstart guide\n```bash\necho quick\n```\n## Usage\n```bash\necho ignored\n```"
        self.assertEqual([b.commands[0] for b in extract(text)], ["echo install", "echo quick"])

    def test_usage_nested_under_target_is_ignored(self):
        text = "## Development\n### Usage\n```bash\necho ignored\n```\n### Commands\n```bash\necho setup\n```"
        self.assertEqual([b.commands for b in extract(text)], [["echo setup"]])

    def test_backslash_continuation_is_joined(self):
        self.assertEqual(extract("## Setup\n```bash\necho one \\\n  two\n```")[0].commands, ["echo one two"])

    def test_console_keeps_only_prompts(self):
        text = "## Setup\n```console\n$ echo ok\nok\n$ echo again\nagain\n```"
        self.assertEqual(extract(text)[0].commands, ["echo ok", "echo again"])

    def test_unsupported_language_is_reported(self):
        block = extract("## Setup\n```zsh\necho no\n```")[0]
        self.assertEqual(block.status, "skipped")
        self.assertIn("unsupported", block.reason)

    def test_install_is_reported_when_higher_priority_exists(self):
        text = "## Development\n```bash\necho dev\n```\n## Install\n```bash\necho install\n```"
        self.assertIn("lower-priority", extract(text)[1].reason)

    def test_no_setup_section_is_explicit(self):
        self.assertEqual(extract("# Project\nNo commands here."), [])

    def test_placeholder_block_is_skipped(self):
        self.assertEqual(extract("## Setup\n```bash\nexport API_KEY=<your-key>\n```")[0].status, "skipped")

    def test_brace_placeholder_is_skipped(self):
        block = extract("## Setup\n```bash\necho {your-project}\n```")[0]
        self.assertIn("placeholder", block.reason)

    def test_alternative_prose_is_skipped(self):
        block = extract("## Setup\nAlternatively, use the Linux instructions:\n```bash\nmake setup\n```")[0]
        self.assertIn("alternative", block.reason)

    def test_alternative_variants_skip_only_second(self):
        for prose in ("or", "Or:", "**or**", "otherwise"):
            text = f"## Setup\n```bash\necho first\n```\n{prose}\n```bash\necho second\n```"
            blocks = extract(text)
            self.assertEqual(blocks[0].status, "usable", prose)
            self.assertEqual(blocks[1].status, "skipped", prose)
            self.assertIn("alternative", blocks[1].reason)

    def test_using_yarn_is_an_alternative(self):
        block = extract("## Setup\nUsing yarn:\n```bash\nyarn install\n```")[0]
        self.assertIn("alternative", block.reason)

    def test_multiple_package_managers_are_skipped(self):
        block = extract("## Setup\n```bash\nnpm install\nyarn install\npnpm install\n```")[0]
        self.assertIn("multiple package managers", block.reason)

    def test_scaffold_dependent_steps_are_skipped(self):
        block = extract("## Setup\n```bash\nnpx create-app demo\ncd demo\nnpm install\nnpm run build\n```")[0]
        self.assertIn("scaffold", block.reason)

    def test_project_library_install_is_skipped(self):
        block = extract("## Setup\n```bash\nnpm install freshclone\n```", package_name="freshclone")[0]
        self.assertIn("library", block.reason)

    def test_own_clone_is_skipped_and_cd_is_rewritten(self):
        text = "## Setup\n```bash\ngit clone https://github.com/acme/demo.git\ncd demo\nnpm install\n```"
        block = extract(text, repo_url="https://github.com/acme/demo")[0]
        self.assertIn("clone", block.reason)
        self.assertEqual(block.commands, ["cd /workspace/repo", "npm install"])

    def test_unsupported_host_commands_are_skipped(self):
        self.assertIn("not supported", extract("## Setup\n```bash\nsudo apt-get update\n```")[0].reason)

    def test_yarn_install_is_not_an_alternative_by_itself(self):
        self.assertEqual(extract("## Setup\n```bash\nyarn install\n```")[0].status, "usable")

    def test_interactive_detection_reports_the_command(self):
        self.assertIn("npm login", extract("## Setup\n```bash\ncd top\n npm login\n```")[0].reason)

    def test_library_install_override_is_supported(self):
        self.assertEqual(extract("## Setup\n```bash\npip install demo\n```", package_name="demo")[0].status, "skipped")


if __name__ == "__main__":
    unittest.main()
