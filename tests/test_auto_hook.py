import json
import unittest
from unittest.mock import patch
from test_jev import resolver
from test_loader_discovery import FakeCtx, _load_plugin_module


class HookCtx(FakeCtx):
    def __init__(self, config=None):
        super().__init__()
        self.config = config or {}
        self.hooks = {}
    def get_config(self, key, default=None):
        return self.config.get(key, default)
    def register_hook(self, name, callback, **kwargs):
        self.hooks[name] = (callback, kwargs)


class AutoHookTest(unittest.TestCase):
    def test_configured_model_reaches_fixed_decisions_endpoint(self):
        plugin = _load_plugin_module('gnothi_model_test')
        ctx = HookCtx({'automatic_check': True, 'jev_remote': True,
                       'decision_model': 'example/decision-model'})
        plugin.register(ctx)
        args = {'data_a': [1, 0], 'data_b': [0, 1], 'paired': True, 'demo_claim': plugin.auto_hook.CLAIM}
        result = ctx.tools['evaluate_difference']['handler'](args)
        ctx.hooks['post_tool_call'][0](tool_name='evaluate_difference', args=args, result=result, session_id='s', turn_id='t', status='ok')
        with resolver('test-secret'), patch('urllib.request.urlopen') as send:
            send.return_value.__enter__.return_value.read.return_value = b'{"answers":{"decision":{"type":"noul","noul":0.5}}}'
            out = ctx.hooks['transform_llm_output'][0](response_text=args['demo_claim'], session_id='s', turn_id='t')
        self.assertIn('0.5', out)
        self.assertIn('example/decision-model', out)
        self.assertNotIn('Jev experimental', out)
        request = send.call_args.args[0]
        self.assertEqual(request.full_url, 'https://openrouter.ai/api/alpha/decisions')
        self.assertEqual(json.loads(request.data)['model'], 'example/decision-model')

    def test_significant_result_does_not_endorse_unqualified_superiority(self):
        plugin = _load_plugin_module('gnothi_scope_test')
        ctx = HookCtx({'automatic_check': True})
        plugin.register(ctx)
        args = {'data_a': [0] * 10, 'data_b': [1] * 10, 'paired': True,
                'entity_a': 'Atlas', 'entity_b': 'Beacon', 'outcome': 'correctness'}
        result = ctx.tools['evaluate_difference']['handler'](args)
        self.assertEqual(json.loads(result)['verdict'], 'supported')
        ctx.hooks['post_tool_call'][0](tool_name='evaluate_difference', args=args, result=result, session_id='s', turn_id='t', status='ok')
        output = ctx.hooks['transform_llm_output'][0](response_text='Beacon is better than Atlas.', session_id='s', turn_id='t')
        self.assertIn('correctness', output)
        self.assertIn('does not establish', output)

    def test_match_is_conservative_and_remote_payload_anonymized(self):
        plugin = _load_plugin_module('gnothi_variants_test')
        ctx = HookCtx({'automatic_check': True, 'jev_remote': True})
        plugin.register(ctx)
        args = {'data_a': [1, 0], 'data_b': [0, 1], 'paired': True,
                'entity_a': 'Atlas', 'entity_b': 'Beacon', 'outcome': 'correctness'}
        observe = ctx.hooks['post_tool_call'][0]
        transform = ctx.hooks['transform_llm_output'][0]
        for text in ['Beacon is not better than Atlas.', 'Beacon is always better than Atlas.',
                     'Beacon causes better outcomes than Atlas.', 'Atlas outperforms Beacon.',
                     'Beacon outperforms Atlas and Cobalt.', 'Beacon outperforms Atlas. Another claim.',
                     'Beacon outperforms Cobalt.', 'Beacon may outperform Atlas.']:
            with self.subTest(text=text), patch(plugin.auto_hook.jev.__name__ + '.ask_noul') as remote:
                observe(tool_name='evaluate_difference', args=args, result=ctx.tools['evaluate_difference']['handler'](args), session_id='s', turn_id='t', status='ok')
                self.assertIsNone(transform(response_text=text, session_id='s', turn_id='t'))
                remote.assert_not_called()
        with patch(plugin.auto_hook.jev.__name__ + '.ask_noul', return_value=.5) as remote:
            observe(tool_name='evaluate_difference', args=args, result=ctx.tools['evaluate_difference']['handler'](args), session_id='s', turn_id='t', status='ok')
            self.assertIn('inconclusive', transform(response_text='Beacon performs better than Atlas', session_id='s', turn_id='t'))
            self.assertNotIn('Atlas', str(remote.call_args))
            self.assertNotIn('Beacon', str(remote.call_args))

    def test_unlabeled_second_comparison_invalidates_binding(self):
        plugin = _load_plugin_module('gnothi_multi_test')
        ctx = HookCtx({'automatic_check': True})
        plugin.register(ctx)
        for args in ({'data_a': [1, 0], 'data_b': [0, 1], 'paired': True,
                      'entity_a': 'Atlas', 'entity_b': 'Beacon', 'outcome': 'correctness'},
                     {'data_a': [1, 0], 'data_b': [0, 1], 'paired': True}):
            ctx.hooks['post_tool_call'][0](tool_name='evaluate_difference', args=args,
                result=ctx.tools['evaluate_difference']['handler'](args), session_id='s', turn_id='t', status='ok')
        self.assertIsNone(ctx.hooks['transform_llm_output'][0](response_text='Beacon outperforms Atlas.', session_id='s', turn_id='t'))

    def test_named_comparison_variant_warns_when_inconclusive(self):
        plugin = _load_plugin_module('gnothi_named_test')
        ctx = HookCtx({'automatic_check': True})
        plugin.register(ctx)
        args = {'data_a': [1, 0], 'data_b': [0, 1], 'paired': True,
                'entity_a': 'Atlas', 'entity_b': 'Beacon', 'outcome': 'correctness'}
        ctx.hooks['post_tool_call'][0](tool_name='evaluate_difference', args=args,
            result=ctx.tools['evaluate_difference']['handler'](args), session_id='s', turn_id='t', status='ok')
        out = ctx.hooks['transform_llm_output'][0](response_text='BEACON outperforms Atlas.', session_id='s', turn_id='t')
        self.assertIn('inconclusive', out)

    def test_unlabeled_evidence_never_matches(self):
        plugin = _load_plugin_module('gnothi_unlabeled_test')
        ctx = HookCtx({'automatic_check': True})
        plugin.register(ctx)
        args = {'data_a': [1, 0], 'data_b': [0, 1], 'paired': True}
        ctx.hooks['post_tool_call'][0](tool_name='evaluate_difference', args=args, result=ctx.tools['evaluate_difference']['handler'](args), session_id='s', turn_id='t', status='ok')
        self.assertIsNone(ctx.hooks['transform_llm_output'][0](response_text='Model B is better than Model A.', session_id='s', turn_id='t'))

    def test_separate_remote_opt_in_does_not_change_result(self):
        plugin = _load_plugin_module('gnothi_remote_test')
        ctx = HookCtx({'automatic_check': True, 'jev_remote': True})
        plugin.register(ctx)
        args = {'data_a': [1, 0], 'data_b': [0, 1], 'paired': True, 'demo_claim': 'Model B is better than Model A.'}
        hook = ctx.hooks['post_tool_call'][0]
        with patch(plugin.auto_hook.jev.__name__ + '.ask_noul', return_value=1.0) as remote:
            hook(tool_name='evaluate_difference', args=args, result=ctx.tools['evaluate_difference']['handler'](args), session_id='s', turn_id='t', status='ok')
            transform = ctx.hooks['transform_llm_output'][0]
            self.assertIsNone(transform(response_text=args['demo_claim'], session_id='other', turn_id='t'))
            self.assertIsNone(transform(response_text=args['demo_claim'], session_id='s', turn_id='other'))
            out = transform(response_text=args['demo_claim'], session_id='s', turn_id='t')
            self.assertIn('inconclusive', out)
            remote.assert_called_once()
            state, question = remote.call_args.args
            self.assertEqual(state['claim'], args['demo_claim'])
            self.assertEqual(state['evidence']['pairs'], 2)
            self.assertEqual(state['evidence']['a_only'], 1)
            self.assertEqual(state['evidence']['b_only'], 1)
            self.assertEqual(state['evidence']['p_value'], 1.0)
            self.assertIn('support', question.lower())
            self.assertNotIn('data_a', str(remote.call_args))
            self.assertIn('experimental', out.lower())
            self.assertIn('non-authoritative', out.lower())
            self.assertIn('1.0', out)

    def test_remote_failure_is_visible_and_keeps_warning(self):
        plugin = _load_plugin_module('gnothi_remote_failure_test')
        ctx = HookCtx({'automatic_check': True, 'jev_remote': True})
        plugin.register(ctx)
        args = {'data_a': [1, 0], 'data_b': [0, 1], 'paired': True, 'demo_claim': plugin.auto_hook.CLAIM}
        result = ctx.tools['evaluate_difference']['handler'](args)
        with patch(plugin.auto_hook.jev.__name__ + '.ask_noul', return_value=None):
            ctx.hooks['post_tool_call'][0](tool_name='evaluate_difference', args=args, result=result, session_id='s', turn_id='t', status='ok')
            out = ctx.hooks['transform_llm_output'][0](response_text=args['demo_claim'], session_id='s', turn_id='t')
        self.assertIn('inconclusive', out)
        self.assertIn('unavailable', out)
        self.assertIn('non-authoritative', out)

    def test_interleaved_sessions_send_only_their_own_aggregate(self):
        plugin = _load_plugin_module('gnothi_sessions_test')
        ctx = HookCtx({'automatic_check': True, 'jev_remote': True})
        plugin.register(ctx)
        for session, a, b in [('a', [1, 0], [0, 1]), ('b', [0, 0, 0], [1, 1, 1])]:
            args = {'data_a': a, 'data_b': b, 'paired': True, 'demo_claim': plugin.auto_hook.CLAIM}
            ctx.hooks['post_tool_call'][0](tool_name='evaluate_difference', args=args, result=ctx.tools['evaluate_difference']['handler'](args), session_id=session, turn_id='t', status='ok')
        with patch(plugin.auto_hook.jev.__name__ + '.ask_noul', return_value=0.4) as remote:
            transform = ctx.hooks['transform_llm_output'][0]
            transform(response_text=plugin.auto_hook.CLAIM, session_id='b', turn_id='t')
            transform(response_text=plugin.auto_hook.CLAIM, session_id='a', turn_id='t')
        self.assertEqual([c.args[0]['evidence']['pairs'] for c in remote.call_args_list], [3, 2])
        self.assertEqual([c.args[0]['evidence']['b_only'] for c in remote.call_args_list], [3, 1])

    def test_opt_in_hook_checks_exact_demo_and_consumes_evidence(self):
        plugin = _load_plugin_module('gnothi_auto_test')
        ctx = HookCtx({'automatic_check': True})
        plugin.register(ctx)
        self.assertTrue(ctx.hooks['transform_llm_output'][1]['hold_stream'])
        args = {'data_a': [1, 0, 0, 0], 'data_b': [0, 1, 0, 0], 'paired': True, 'demo_claim': 'Model B is better than Model A.'}
        result = ctx.tools['evaluate_difference']['handler'](args)
        ctx.hooks['post_tool_call'][0](tool_name='evaluate_difference', args=args, result=result,
                                       session_id='s', turn_id='t', status='ok')
        transform = ctx.hooks['transform_llm_output'][0]
        out = transform(response_text='Model B is better than Model A.', session_id='s', turn_id='t')
        self.assertIn('inconclusive', out.lower())
        self.assertIsNone(transform(response_text='Model B is better than Model A.', session_id='s', turn_id='t'))
