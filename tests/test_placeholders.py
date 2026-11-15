import unittest

from freshclone.extractor import extract


class BracePlaceholderTests(unittest.TestCase):
    def test_only_supported_brace_names_are_placeholders(self):
        block = extract("## Setup\n```bash\nawk '{print $1}' f\n${HOME}\necho {project_name}\n```")[0]
        self.assertEqual(block.status, "skipped")
        self.assertIn("{project_name}", block.reason)

    def test_shell_braces_are_not_placeholders(self):
        block = extract("## Setup\n```bash\nawk '{print $1}' f\n${HOME}\n```")[0]
        self.assertEqual(block.status, "usable")


if __name__ == "__main__":
    unittest.main()
