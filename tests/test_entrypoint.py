import unittest
from mock import patch
from environment_backend.entrypoint import handler
import json


class TestEntrypoint(unittest.TestCase):

    def setUp(self):
        patcher1 = patch('environment_backend.entrypoint.UserEnvironment')
        self.addCleanup(patcher1.stop)
        self.mock_user_env = patcher1.start()

    def test_invalid_path(self):
        with self.assertRaises(TypeError) as cm:
            handler({"resource-path": "/"}, {})
        result_json = json.loads(str(cm.exception))
        self.assertEqual(result_json.get('http_status'), 400)
        self.assertEqual(result_json.get('data').get('errors')[0].get('detail'),  # NOQA
                         "Invalid path /")
        self.assertEqual(len(self.mock_user_env.mock_calls), 0)

    def test_ping_endpoint(self):
        event = {
          "resource-path": "/environment/ping",
          "http-method": "GET",
        }
        result = handler(event, {})
        self.assertEqual(result.get('http_status'), 200)
        self.assertTrue("version" in result.get('data').get('meta'))
        self.assertEqual(len(self.mock_user_env.mock_calls), 0)
