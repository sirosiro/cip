import unittest
import os
import shutil
import signal
import tempfile
from cip_bridge.transport.fs_bus import FSBus

# Global handler to prevent SIGUSR1 from terminating the test process
def handle_sigusr1(signum, frame):
    pass

class TestFSBus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only set if we can
        try:
            signal.signal(signal.SIGUSR1, handle_sigusr1)
        except (ValueError, AttributeError):
            pass

    def setUp(self):
        # Create a temporary base directory for the test bus
        self.test_dir = tempfile.mkdtemp()
        self.bus_id = "test_node"
        self.bus = FSBus(self.bus_id, base_dir=self.test_dir)

    def tearDown(self):
        # Remove the temporary directory after the test
        shutil.rmtree(self.test_dir)

    def test_setup_and_cleanup(self):
        self.bus.setup()
        self.assertTrue(os.path.exists(self.bus.bus_dir))
        self.assertTrue(os.path.exists(self.bus.pid_path))
        self.assertTrue(os.path.exists(self.bus.inbox_dir))
        
        # Check if PID is correct
        with open(self.bus.pid_path, "r") as f:
            pid = int(f.read().strip())
        self.assertEqual(pid, os.getpid())

    def test_send_and_receive(self):
        self.bus.setup()
        
        # Mocking signal behavior for send (not really needed but to avoid interference)
        target_id = self.bus_id
        message = "Test message content"
        
        success = self.bus.send(target_id, message)
        self.assertTrue(success)
        
        # Verify message written correctly
        files = os.listdir(self.bus.inbox_dir)
        self.assertEqual(len(files), 1)
        with open(os.path.join(self.bus.inbox_dir, files[0]), "r") as f:
            raw_content = f.read()
            self.assertIn(f"[FROM: @{self.bus_id}]", raw_content)
            self.assertIn(message, raw_content)
            
        # Receive (consume) the message
        received = self.bus.receive()
        self.assertIsNotNone(received)
        self.assertIn(message, received)
        
        # Inbox should be empty after receive
        self.assertIsNone(self.bus.receive())

    def test_target_not_found(self):
        self.bus.setup()
        success = self.bus.send("non_existent_node", "hello")
        self.assertFalse(success)

if __name__ == "__main__":
    unittest.main()