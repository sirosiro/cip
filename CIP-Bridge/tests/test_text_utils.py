import unittest
from cip_bridge.utils.text_utils import strip_ansi, remove_thinking_block, remove_ui_noise, extract_tag_content

class TestTextUtils(unittest.TestCase):
    def test_strip_ansi(self):
        text_with_ansi = "\x1b[31mRed Text\x1b[0m and \x1b[1mBold Text\x1b[0m"
        self.assertEqual(strip_ansi(text_with_ansi), "Red Text and Bold Text")
        
    def test_remove_thinking_block(self):
        text_with_thinking = "Hello <thinking>Secret thought</thinking>World"
        self.assertEqual(remove_thinking_block(text_with_thinking), "Hello World")
        
        # Nested-like structure (should handle sequentially)
        text_multiple = "<thinking>A</thinking>B<thinking>C</thinking>"
        self.assertEqual(remove_thinking_block(text_multiple), "B")

    def test_remove_ui_noise(self):
        text = "✦⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏✦\n╭─╮\n│ Message │\n╰─╯\nUsing: some.md file\n>   Type your message"
        cleaned = remove_ui_noise(text)
        self.assertIn("> ", cleaned)
        self.assertNotIn("✦", cleaned)
        self.assertNotIn("╭─╮", cleaned)
        self.assertNotIn("Using:", cleaned)

    def test_extract_tag_content(self):
        text = "Prefix [TAG]Inside[/TAG] Suffix"
        content, end_idx = extract_tag_content(text, "[TAG]", "[/TAG]")
        self.assertEqual(content, "[TAG]Inside[/TAG]")
        self.assertEqual(text[end_idx:], " Suffix")

        content, end_idx = extract_tag_content(text, "[NON]", "[/NON]")
        self.assertIsNone(content)
        self.assertEqual(end_idx, -1)

if __name__ == "__main__":
    unittest.main()

