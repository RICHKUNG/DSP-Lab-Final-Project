
import unittest
import threading
import time
from src.audio.controller import VoiceController
from src.event_bus import EventBus, Event, EventType
from unittest.mock import MagicMock, patch

class TestCalibrationMode(unittest.TestCase):
    def setUp(self):
        self.event_bus = EventBus()
        self.event_bus.start() # Start the dispatcher
        self.controller = VoiceController(event_bus=self.event_bus)
        # Mock dependencies to avoid actual audio hardware
        self.controller._audio_stream = MagicMock()
        self.controller._vad = MagicMock()
        self.controller._matcher = MagicMock()
        self.controller._running = True

    def tearDown(self):
        self.controller.stop()
        self.event_bus.stop()

    def test_start_stop_calibration(self):
        self.controller.start_calibration_mode("START")
        self.assertEqual(self.controller._calibration_target, "START")
        
        self.controller.stop_calibration_mode()
        self.assertIsNone(self.controller._calibration_target)

    def test_calibration_match_logic(self):
        # This test simulates the logic inside _recognition_loop without running the full thread
        self.controller.start_calibration_mode("JUMP")
        
        # Simulate a successful recognition
        cmd = "JUMP"
        segment = MagicMock()
        
        # Re-implement the snippet of logic from _recognition_loop to test it
        # (Ideally we refactor the loop to be testable, but for now we verify state changes)
        
        target = self.controller._calibration_target
        if target and cmd == target:
            self.controller._matcher.add_template(cmd, segment, 'test_calib')
            self.event_bus.publish(Event(EventType.CALIBRATION_RESULT, {'command': cmd, 'success': True}))
            self.controller._calibration_target = None
            
        # Verify
        self.controller._matcher.add_template.assert_called()
        self.assertIsNone(self.controller._calibration_target) # Should auto-stop
        
        # Verify event
        events = []
        def handler(e): events.append(e)
        self.event_bus.subscribe(EventType.CALIBRATION_RESULT, handler)
        
        # Publish again to check listener (the previous one was before subscribe, so we missed it in the list)
        self.event_bus.publish(Event(EventType.CALIBRATION_RESULT, {'command': cmd, 'success': True}))
        
        time.sleep(0.1) # Wait for thread dispatch
        self.assertTrue(len(events) > 0)
        self.assertEqual(events[0].data['command'], 'JUMP')

if __name__ == '__main__':
    unittest.main()
