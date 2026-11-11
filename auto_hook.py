"""Opt-in, deliberately narrow paired-binary demo audit; no durable state."""
import json
import re
import threading
import time
from collections import OrderedDict

from . import tools, jev

CLAIM = 'Model B is better than Model A.'


def _binding(args):
    if args.get('demo_claim') == CLAIM and not any(k in args for k in ('entity_a', 'entity_b', 'outcome')):
        return 'Model A', 'Model B'
    a, b = args.get('entity_a'), args.get('entity_b')
    if args.get('outcome') != 'correctness' or not all(
        isinstance(x, str) and re.fullmatch(r'[A-Za-z][A-Za-z0-9]*(?: [A-Za-z0-9]+){0,3}', x)
        and len(x) <= 60 for x in (a, b)):
        return None
    if a.casefold() == b.casefold() or a.casefold() in b.casefold() or b.casefold() in a.casefold():
        return None
    return a, b


def _matches(text, binding):
    if not isinstance(text, str) or len(text) > 300:
        return False
    a, b = (re.escape(x).replace(r'\ ', r'\s+') for x in binding)
    return bool(re.fullmatch(
        rf'\s*{b}\s+(?:is\s+better\s+than|outperforms|performs\s+better\s+than)\s+{a}\s*[.]?\s*',
        text, re.IGNORECASE))


class DemoAudit:
    def __init__(self, remote=False, model=jev.DEFAULT_MODEL):
        self.remote = remote is True
        self.model = model
        self.lock = threading.Lock()
        self.pending = OrderedDict()

    @staticmethod
    def key(session_id, turn_id):
        if all(isinstance(x, str) and 0 < len(x) <= 256 for x in (session_id, turn_id)):
            return session_id, turn_id
        return None

    def observe(self, tool_name=None, args=None, result=None, session_id=None, turn_id=None, status=None, **kwargs):
        key = self.key(session_id, turn_id)
        if not key or tool_name != 'evaluate_difference' or status != 'ok' or not isinstance(args, dict):
            return
        marker = object()
        with self.lock:
            now = time.monotonic()
            for old in list(self.pending):
                if now - self.pending[old][0] > 300:
                    del self.pending[old]
            if key in self.pending:
                self.pending[key] = (now, None)
                return
            self.pending[key] = (now, marker)
            while len(self.pending) > 128:
                self.pending.popitem(last=False)
        a, b = args.get('data_a'), args.get('data_b')
        binding = _binding(args)
        if (not binding or args.get('paired') is not True or not isinstance(a, list) or not isinstance(b, list)
                or not 2 <= len(a) == len(b) <= 200 or any(type(x) is not int or x not in (0, 1) for x in a + b)
                or args.get('alpha') not in (None, 0.05) or args.get('correction') not in (None, 'none')):
            return
        try:
            received = json.loads(result) if isinstance(result, str) and len(result) <= 16384 else None
            checked = json.loads(tools.evaluate_difference({'data_a': a, 'data_b': b, 'paired': True}))
            if not isinstance(received, dict) or received.get('verdict') != checked.get('verdict') or received.get('p_value') != checked.get('p_value'):
                return
        except (ValueError, TypeError):
            return
        with self.lock:
            if self.pending.get(key, (None, None))[1] is marker:
                evidence = {'pairs': len(a),
                            'a_only': sum(x == 1 and y == 0 for x, y in zip(a, b)),
                            'b_only': sum(x == 0 and y == 1 for x, y in zip(a, b)),
                            'p_value': checked['p_value']}
                self.pending[key] = (now, (checked['verdict'], evidence, binding))

    def transform(self, response_text=None, session_id=None, turn_id=None, **kwargs):
        key = self.key(session_id, turn_id)
        if not key:
            return None
        with self.lock:
            record = self.pending.pop(key, None)
        if not record or time.monotonic() - record[0] > 300:
            return None
        if not isinstance(record[1], tuple):
            return None
        verdict, evidence, binding = record[1]
        if not _matches(response_text, binding):
            return None
        output = response_text
        if verdict != 'supported':
            output += '\n\nGnothi: The paired correctness comparison is ' + verdict + '; it does not establish this superiority claim.'
        else:
            output += '\n\nGnothi: The paired correctness comparison supports a difference in the tested setting; it does not establish unqualified superiority.'
        if self.remote:
            score = jev.ask_noul({'claim': CLAIM, 'evidence': evidence},
                                 'For paired binary correctness outcomes, pairs is the sample size, a_only and b_only count discordant pairs won by A and B, and p_value is the two-sided exact McNemar p-value. Does this evidence support the claim?', enabled=True, model=self.model)
            if score is None:
                output += '\n\nOpenRouter experimental, non-authoritative advisory: unavailable.'
            else:
                output += f'\n\nOpenRouter experimental, non-authoritative advisory score ({self.model}): {score}. This is not a probability that the claim is true.'
        return output if output != response_text else None
