import unittest
import json
from unittest.mock import patch, MagicMock
from app.fetcher import Fetcher

class TestFetcher(unittest.TestCase):

    @patch('app.fetcher.requests.get')
    def test_fetch_web(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = 'Mocked content'
        mock_get.return_value = mock_response

        config = {'websites': [{'url': 'http://example.com', 'type': 'web'}], 'history_file': 'test_history.json'}
        fetcher = Fetcher(config)
        result = fetcher.fetch_web('http://example.com')
        self.assertEqual(result['content'], 'Mocked content')

    @patch('app.fetcher.feedparser.parse')
    def test_fetch_youtube(self, mock_parse):
        mock_feed = MagicMock()
        mock_feed.entries = [MagicMock(link='http://youtube.com/video', title='Mocked Video')]
        mock_parse.return_value = mock_feed

        config = {'websites': [{'url': 'http://youtube.com/channel', 'type': 'youtube'}], 'history_file': 'test_history.json'}
        fetcher = Fetcher(config)
        result = fetcher.fetch_youtube('http://youtube.com/channel')
        self.assertEqual(result['title'], 'Mocked Video')
        self.assertEqual(result['url'], 'http://youtube.com/video')

    def test_load_history(self):
        config = {'websites': [], 'history_file': 'test_history.json'}
        fetcher = Fetcher(config)
        fetcher.history = [{"timestamp": "2023-06-12T10:00:00", "posts": []}]
        fetcher.save_history()

        new_fetcher = Fetcher(config)
        self.assertEqual(new_fetcher.history, [{"timestamp": "2023-06-12T10:00:00", "posts": []}])

    def test_save_history(self):
        config = {'websites': [], 'history_file': 'test_history.json'}
        fetcher = Fetcher(config)
        fetcher.history = [{"timestamp": "2023-06-12T10:00:00", "posts": []}]
        fetcher.save_history()

        with open('test_history.json', 'r') as file:
            history = json.load(file)
            self.assertEqual(history, [{"timestamp": "2023-06-12T10:00:00", "posts": []}])

if __name__ == '__main__':
    unittest.main()
