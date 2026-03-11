import unittest
from unittest.mock import patch, MagicMock, mock_open
import os
import time
import threading

# We need to mock os.environ and other os level calls before importing bridge.py
# that might execute them at module level or during init.
from cip_bridge.core.bridge import BridgeCore

class TestBridgeCore(unittest.TestCase):
    @patch('cip_bridge.core.bridge.FSBus')
    @patch('cip_bridge.core.bridge.ProtocolStack')
    @patch('cip_bridge.core.bridge.NegotiationManager')
    @patch('os.pipe')
    @patch('fcntl.fcntl')
    def setUp(self, mock_fcntl, mock_pipe, mock_nego, mock_proto, mock_fsbus):
        mock_pipe.return_value = (1, 2)
        # Prevent actually calling os.getcwd() if it matters
        with patch('os.getcwd', return_value='/dummy/path/my_node'):
            self.bridge = BridgeCore(cmd=["echo", "test"], bus_id="my_node", base_dir="/dummy/bus")

    @patch('os.write')
    @patch('time.sleep')
    def test_inject_notification(self, mock_sleep, mock_write):
        self.bridge.master_fd = 99 # Mock FD
        
        self.bridge.inject_notification()
        
        self.assertTrue(mock_write.called)
        write_calls = mock_write.call_args_list
        self.assertEqual(len(write_calls), 2)
        
        first_call_content = write_calls[0][0][1].decode('utf-8')
        self.assertIn("新着メッセージがあります", first_call_content)
        self.assertIn("read_file で current_message.md を読め", first_call_content)
        self.assertEqual(write_calls[1][0][1].decode('utf-8'), '\r')

    @patch('threading.Thread')
    def test_inject_system_message(self, mock_thread_class):
        self.bridge.master_fd = 99
        mock_thread_instance = MagicMock()
        mock_thread_class.return_value = mock_thread_instance
        
        self.bridge.inject_system_message("Important Update")
        
        mock_thread_class.assert_called_once()
        _, kwargs = mock_thread_class.call_args
        self.assertTrue(kwargs.get('daemon'))
        
        target_func = kwargs.get('target')
        self.assertTrue(callable(target_func))

        mock_thread_instance.start.assert_called_once()

    @patch('os.write')
    def test_handle_signal(self, mock_write):
        self.bridge.pipe_w = 2
        self.bridge.handle_signal(None, None)
        mock_write.assert_called_once_with(2, b'\x00')

if __name__ == "__main__":
    unittest.main()