import unittest
from cip_bridge.utils.text_utils import strip_ansi, remove_thinking_block, remove_ui_noise, extract_tag_content

class TestTextUtils(unittest.TestCase):
    def test_strip_ansi(self):
        text_with_ansi = "\x1b[31mRed Text\x1b[0m and \x1b[1mBold Text\x1b[0m"
        self.assertEqual(strip_ansi(text_with_ansi), "Red Text and Bold Text")
        
        # Test OSC sequence (Operating System Command) \x1b] ... \x07
        text_with_osc = "\x1b]0;Title\x07Hello"
        self.assertEqual(strip_ansi(text_with_osc), "Hello")

        # Test OSC with string terminator \x1b\
        text_with_osc_st = "\x1b]0;Title\x1b\\World"
        self.assertEqual(strip_ansi(text_with_osc_st), "World")

    def test_remove_thinking_block(self):
        text_with_thinking = "Hello <thinking>Secret thought</thinking>World"
        self.assertEqual(remove_thinking_block(text_with_thinking), "Hello World")
        
        # Nested-like structure (should handle sequentially)
        text_multiple = "<thinking>A</thinking>B<thinking>C</thinking>"
        self.assertEqual(remove_thinking_block(text_multiple), "B")

        # Test incomplete block (missing closing)
        text_incomplete = "Hello <thinking>Secret"
        self.assertEqual(remove_thinking_block(text_incomplete), "Hello <thinking>Secret")

    def test_remove_ui_noise(self):
        text = "✦⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏✦\n╭─╮\n│ Message │\n╰─╯\nUsing: some.md file\n>   Type your message"
        cleaned = remove_ui_noise(text)
        self.assertIn("> ", cleaned)
        self.assertNotIn("✦", cleaned)
        self.assertNotIn("╭─╮", cleaned)
        self.assertNotIn("Using:", cleaned)

        # Test tag preservation inside noise.
        # Note: remove_ui_noise strips border_chars first, so `temp_line`
        # appended for lines with `[` will have the border stripped.
        text_with_tag = "│ [NEED_CONSENSUS] │"
        cleaned_tag = remove_ui_noise(text_with_tag)
        self.assertEqual(cleaned_tag, " [NEED_CONSENSUS] ")

        # Test prompt lines removal
        text_prompts = "> \n+ \n│ > \n│ + \nHello"
        cleaned_prompts = remove_ui_noise(text_prompts)
        self.assertEqual(cleaned_prompts, "Hello")

        # Test known noise lines removal
        text_known_noise = "Rebooting the humor module\n(esc to cancel,\nno sandbox\nWaiting for user confirmation\nReal text"
        cleaned_known_noise = remove_ui_noise(text_known_noise)
        self.assertEqual(cleaned_known_noise, "Real text")

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
