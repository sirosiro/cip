import unittest
from cip_bridge.core.negotiator import NegotiationManager, BridgeState
from cip_bridge.protocol.stack import Packet

class TestNegotiationManager(unittest.TestCase):
    def setUp(self):
        self.nego = NegotiationManager("my_node")

    def test_state_updates(self):
        pkt = Packet(type="NEED_CONSENSUS", content="Request", target_id="target_node")
        self.nego.update_state(pkt)
        self.assertEqual(self.nego.get_partner(), "target_node")
        # Transmitter's update_state should NOT change the last_received_type.
        # It should only be updated by record_receive.
        self.assertIsNone(self.nego.last_received_type)
        
        self.nego.record_receive("ACCEPTED")
        self.assertEqual(self.nego.last_received_type, "ACCEPTED")

    def test_routing_logic(self):
        # 1. Start a negotiation
        pkt_need = Packet(type="NEED_CONSENSUS", content="Req", target_id="worker")
        # should_route should be called BEFORE update_state
        self.assertTrue(self.nego.should_route(pkt_need))
        self.nego.update_state(pkt_need)
        self.assertEqual(self.nego.get_route(pkt_need), "worker")
        
        # 2. Receive reply (simulated by processing inbox)
        self.nego.record_receive("ACCEPTED")
        
        # 3. Echo-back prevention: Should NOT route another ACCEPTED if we just received one
        pkt_reply_echo = Packet(type="ACCEPTED", content="Ok_echo")
        self.assertFalse(self.nego.should_route(pkt_reply_echo))
        
        # 4. Routing of CONFLICT should still work after ACCEPTED
        pkt_conflict = Packet(type="CONFLICT", content="Err")
        self.assertTrue(self.nego.should_route(pkt_conflict))
        self.assertEqual(self.nego.get_route(pkt_conflict), "worker")

    def test_set_mode_auto(self):
        self.nego.set_mode(BridgeState.AUTO)
        self.assertEqual(self.nego.mode, BridgeState.AUTO)
        self.assertEqual(self.nego.negotiation_count, 0)
        self.assertEqual(len(self.nego.sent_content_hashes), 0)

    def test_update_state_completed_resets_mode(self):
        self.nego.set_mode(BridgeState.AUTO)
        pkt = Packet(type="COMPLETED", content="Done")
        self.nego.update_state(pkt)
        self.assertEqual(self.nego.mode, BridgeState.BYPASS)

    def test_update_state_failed_resets_mode(self):
        self.nego.set_mode(BridgeState.AUTO)
        pkt = Packet(type="FAILED", content="Error")
        self.nego.update_state(pkt)
        self.assertEqual(self.nego.mode, BridgeState.BYPASS)

    def test_should_route_duplicate_content(self):
        pkt1 = Packet(type="NEED_CONSENSUS", content="Same Content", target_id="worker")
        self.nego.update_state(pkt1)
        
        # Another packet with the same normalized content
        pkt2 = Packet(type="NEED_CONSENSUS", content="Same Content!!!", target_id="worker")
        self.assertFalse(self.nego.should_route(pkt2))

    def test_should_route_empty_content(self):
        # Empty after normalization (e.g. only symbols)
        pkt = Packet(type="NEED_CONSENSUS", content="???", target_id="worker")
        self.assertFalse(self.nego.should_route(pkt))

    def test_get_route_completed_failed(self):
        pkt1 = Packet(type="COMPLETED", content="Done")
        self.assertIsNone(self.nego.get_route(pkt1))

        pkt2 = Packet(type="FAILED", content="Err")
        self.assertIsNone(self.nego.get_route(pkt2))

    def test_get_route_accepted_conflict_no_target(self):
        self.nego.set_partner("some_worker")
        pkt = Packet(type="ACCEPTED", content="Ok") # No target_id specified
        self.assertEqual(self.nego.get_route(pkt), "some_worker")

    def test_get_route_unknown_type(self):
        pkt = Packet(type="UNKNOWN_TYPE", content="Content")
        self.assertIsNone(self.nego.get_route(pkt))

    def test_record_receive_need_consensus_resets_history(self):
        # Prepare history
        self.nego.sent_content_hashes.append("fake_hash")
        self.nego.record_receive("NEED_CONSENSUS")
        self.assertEqual(len(self.nego.sent_content_hashes), 0)

    def test_update_state_need_consensus_in_auto_mode(self):
        self.nego.set_mode(BridgeState.AUTO)
        pkt = Packet(type="NEED_CONSENSUS", content="Req")
        self.nego.update_state(pkt)
        self.assertEqual(self.nego.negotiation_count, 1)

    def test_update_state_history_truncation(self):
        # Add 100 fake hashes
        for i in range(100):
            self.nego.sent_content_hashes.append(f"hash_{i}")
            
        pkt = Packet(type="ACCEPTED", content="New Content")
        self.nego.update_state(pkt)
        self.assertEqual(len(self.nego.sent_content_hashes), 100) # Should have popped the oldest one

if __name__ == "__main__":
    unittest.main()
