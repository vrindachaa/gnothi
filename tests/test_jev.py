import sys
import unittest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
from types import ModuleType


def resolver(secret):
    scope = ModuleType('agent.secret_scope')
    scope.get_secret = lambda name: secret
    return patch.dict(sys.modules, {'agent.secret_scope': scope})

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class JevTests(unittest.TestCase):
    def test_disabled_returns_unavailable(self):
        import jev
        self.assertIsNone(jev.ask_noul('hello', 'Is this true?'))

    def test_active_profile_resolver_overrides_process_environment(self):
        import jev
        import types
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = b'{"answers":{"decision":{"type":"noul","noul":0.73}}}'
        scope = types.ModuleType('agent.secret_scope')
        scope.get_secret = MagicMock(return_value='profile-secret')
        with patch.dict(sys.modules, {'agent.secret_scope': scope}), patch.dict('os.environ', {'OPENROUTER_API_KEY': 'wrong-profile'}), patch('urllib.request.urlopen', return_value=response) as send:
            self.assertEqual(jev.ask_noul('s', 'q', enabled=True), .73)
        scope.get_secret.assert_called_once_with('OPENROUTER_API_KEY')
        self.assertEqual(send.call_args.args[0].get_header('Authorization'), 'Bearer profile-secret')

    def test_missing_profile_api_or_key_never_falls_back_to_environment(self):
        import jev
        import types
        for module in (None, types.ModuleType('agent.secret_scope')):
            with self.subTest(module=module), patch.dict(sys.modules, {'agent.secret_scope': module}), patch.dict('os.environ', {'OPENROUTER_API_KEY': 'ambient-secret'}), patch('urllib.request.urlopen') as send:
                self.assertIsNone(jev.ask_noul('s', 'q', enabled=True))
                send.assert_not_called()
        scope = types.ModuleType('agent.secret_scope')
        scope.get_secret = MagicMock(return_value=None)
        with patch.dict(sys.modules, {'agent.secret_scope': scope}), patch.dict('os.environ', {'OPENROUTER_API_KEY': 'ambient-secret'}), patch('urllib.request.urlopen') as send:
            self.assertIsNone(jev.ask_noul('s', 'q', enabled=True))
            send.assert_not_called()

    def test_success_uses_decisions_protocol(self):
        import jev
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps({'answers': {'decision': {'type': 'noul', 'noul': .73}}}).encode()
        with resolver('test-secret'), patch('urllib.request.urlopen', return_value=response) as send:
            self.assertEqual(jev.ask_noul({'text': 'sample'}, 'Is it relevant?', enabled=True, timeout=2), .73)
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, 'https://openrouter.ai/api/alpha/decisions')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(request.get_header('Authorization'), 'Bearer test-secret')
        self.assertEqual(send.call_args.kwargs['timeout'], 2)
        self.assertEqual(json.loads(request.data), {'model': 'typesafe/jev-1.14', 'state': {'text': 'sample'}, 'questions': {'decision': {'type': 'noul', 'instructions': 'Is it relevant?'}}})
    def test_invalid_model_identifiers_never_send(self):
        import jev
        with resolver('test-secret'), patch('urllib.request.urlopen') as send:
            for model in (None, True, '', 'model', 'https://evil.example/model',
                          'vendor/model?x=1', 'vendor/model\n', 'vendor/../model',
                          ' vendor/model', 'vendor/' + 'a' * 256):
                with self.subTest(model=model):
                    self.assertIsNone(jev.ask_noul('s', 'q', enabled=True, model=model))
            send.assert_not_called()

    def test_fail_closed_for_network_and_bad_responses(self):
        import jev
        cases = [OSError('secret'), b'not json', b'{}',
                 b'{"answers":{"decision":{"type":"choice","noul":0.9}}}',
                 b'{"answers":{"decision":{"type":"noul","noul":2}}}',
                 b'{"answers":{"decision":{"type":"noul","noul":true}}}',
                 b'x' * 65537]
        with resolver('secret'):
            for case in cases:
                with self.subTest(case=str(case)[:50]), patch('urllib.request.urlopen') as send:
                    if isinstance(case, Exception):
                        send.side_effect = case
                    else:
                        send.return_value.__enter__.return_value.read.return_value = case
                    self.assertIsNone(jev.ask_noul('s', 'question?', enabled=True))

    def test_invalid_or_unconsented_inputs_never_send(self):
        import jev
        with resolver('secret'), patch('urllib.request.urlopen') as send:
            for state, question, enabled, timeout in [
                ('x', 'q', False, 1), ('x' * 20000, 'q', True, 1),
                ('x', '', True, 1), ('x', 'q' * 5000, True, 1),
                ('x', 'q', True, 0), ('x', 'q', True, float('nan')),
                (object(), 'q', True, 1), ('x', 'q', 1, 1),
            ]:
                with self.subTest(state=str(state)[:10], timeout=timeout):
                    self.assertIsNone(jev.ask_noul(state, question, enabled=enabled, timeout=timeout))
            send.assert_not_called()
        with patch.dict('os.environ', {}, clear=True), patch('urllib.request.urlopen') as send:
            self.assertIsNone(jev.ask_noul('x', 'q', enabled=True))
            send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
