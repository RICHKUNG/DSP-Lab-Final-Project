
import unittest
import json
import os
import shutil
import time
from src.game.server import GameServer
from src.event_bus import EventBus

class TestLeaderboard(unittest.TestCase):
    def setUp(self):
        self.event_bus = EventBus()
        self.test_user = "TestPlayer"
        self.server = GameServer(event_bus=self.event_bus, user_name=self.test_user)
        self.server.leaderboard_file = "test_leaderboard.json"
        
        # Clean up before test
        if os.path.exists(self.server.leaderboard_file):
            os.remove(self.server.leaderboard_file)

    def tearDown(self):
        # Clean up after test
        if os.path.exists(self.server.leaderboard_file):
            os.remove(self.server.leaderboard_file)

    def test_leaderboard_creation_and_update(self):
        # Create a mock client for SocketIO
        client = self.server.socketio.test_client(self.server.app)
        
        # Simulate Game Over
        score = 150
        client.emit('game_over', {'score': score})
        
        # Check if file exists
        self.assertTrue(os.path.exists(self.server.leaderboard_file))
        
        # Check content
        with open(self.server.leaderboard_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['name'], self.test_user)
        self.assertEqual(data[0]['score'], score)
        
        # Check response
        received = client.get_received()
        # Find 'leaderboard_update' event
        leaderboard_update = next((x for x in received if x['name'] == 'leaderboard_update'), None)
        self.assertIsNotNone(leaderboard_update)
        self.assertEqual(len(leaderboard_update['args'][0]['leaderboard']), 1)
        self.assertEqual(leaderboard_update['args'][0]['leaderboard'][0]['score'], score)

    def test_leaderboard_sorting(self):
        # Pre-fill leaderboard
        initial_data = [
            {'name': 'Player1', 'score': 100, 'date': '2025-01-01'},
            {'name': 'Player2', 'score': 200, 'date': '2025-01-01'},
        ]
        with open(self.server.leaderboard_file, 'w', encoding='utf-8') as f:
            json.dump(initial_data, f)
            
        client = self.server.socketio.test_client(self.server.app)
        
        # New high score
        client.emit('game_over', {'score': 300})
        
        with open(self.server.leaderboard_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        self.assertEqual(len(data), 3)
        self.assertEqual(data[0]['name'], self.test_user)
        self.assertEqual(data[0]['score'], 300) # Should be first
        self.assertEqual(data[1]['name'], 'Player2')
        self.assertEqual(data[2]['name'], 'Player1')

if __name__ == '__main__':
    unittest.main()
