import unittest
from cip_bridge.protocol.stack import ProtocolStack, Packet

class TestProtocolStack(unittest.TestCase):
    def setUp(self):
        self.stack = ProtocolStack("my_node")

    def test_parse_need_consensus(self):
        raw_text = """
        Thinking...
        [NEED_CONSENSUS] @target_node
        Request: Please check this file.
        [/NEED_CONSENSUS]
        Noise...
        """
        packets = self.stack.parse(raw_text)
        self.assertEqual(len(packets), 1)
        pkt = packets[0]
        self.assertEqual(pkt.type, "NEED_CONSENSUS")
        self.assertEqual(pkt.target_id, "target_node")
        self.assertIn("Request: Please check this file.", pkt.content)
        self.assertEqual(pkt.sender_id, "my_node")

    def test_parse_accepted_and_conflict(self):
        # Multiple tags in one stream
        raw_text = """
        [ACCEPTED]
        Okay, proceed.
        [/ACCEPTED]
        [CONFLICT]
        Wait, there's a problem.
        [/CONFLICT]
        """
        # Our current parse() implementation extracts only the first occurrence for each type
        # because the original bridge.py only handled one tag per turn.
        packets = self.stack.parse(raw_text)
        self.assertEqual(len(packets), 2)
        
        pkt_types = [p.type for p in packets]
        self.assertIn("ACCEPTED", pkt_types)
        self.assertIn("CONFLICT", pkt_types)

    def test_ignore_other_from_tags(self):
        # Should ignore tags that have [FROM: @other] unless it's @my_node
        raw_text = """
        [NEED_CONSENSUS] @target
        [FROM: @other]
        Request content.
        [/NEED_CONSENSUS]
        """
        packets = self.stack.parse(raw_text)
        self.assertEqual(len(packets), 0) # Ignored

        raw_text_self = """
        [NEED_CONSENSUS] @target
        [FROM: @my_node]
        Request content.
        [/NEED_CONSENSUS]
        """
        packets_self = self.stack.parse(raw_text_self)
        self.assertEqual(len(packets_self), 1) # Allowed

    def test_parse_system_tag(self):
        # [SYSTEM] tag without newline
        raw_text = "[SYSTEM]@worker status[/SYSTEM]"
        packets = self.stack.parse(raw_text)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0].type, "SYSTEM")
        self.assertEqual(packets[0].target_id, "worker")
        self.assertIn("status", packets[0].content)

    def test_serialize(self):
        pkt = Packet(type="ACCEPTED", content="Test message")
        serialized = self.stack.serialize(pkt)
        self.assertEqual(serialized, "Test message")

if __name__ == "__main__":
    unittest.main()
