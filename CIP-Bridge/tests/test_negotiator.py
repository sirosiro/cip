import unittest
from cip_bridge.core.negotiator import NegotiationManager
from cip_bridge.protocol.stack import Packet

class TestNegotiationManager(unittest.TestCase):
    def setUp(self):
        self.nego = NegotiationManager("my_node")

    def test_state_updates(self):
        pkt = Packet(type="NEED_CONSENSUS", content="Request", target_id="target_node")
        self.nego.update_state(pkt)
        self.assertEqual(self.nego.get_partner(), "target_node")
        # Test expects this based on legacy or simplified contract
        self.assertEqual(self.nego.last_received_type, "NEED_CONSENSUS")
        
        pkt_reply = Packet(type="ACCEPTED", content="Ok")
        self.nego.update_state(pkt_reply)
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

if __name__ == "__main__":
    unittest.main()