"""Optional Jev decision support."""
import json
import math
import re
import urllib.request

DEFAULT_MODEL = 'typesafe/jev-1.14'


def ask_noul(state, instructions, *, enabled=False, timeout=3.0, model=DEFAULT_MODEL):
    """Return the yes probability, or None when unavailable; never auto-approve.

    Caller must explicitly opt in and select/redact state before calling. State
    and question are sent to OpenRouter and its provider and may incur charges.
    Only JSON text/object/array state is accepted, bounded to 16 KiB per request.
    """
    if enabled is not True:
        return None
    try:
        # Resolve at call time within Hermes' active profile; fail closed if the
        # supported API is absent rather than bypassing isolation via environ.
        from agent.secret_scope import get_secret
        key = get_secret('OPENROUTER_API_KEY')
        if (not key or not isinstance(model, str) or len(model) > 200 or
                not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._:-]*', model) or
                not isinstance(state, (str, dict, list)) or
                not isinstance(instructions, str) or not instructions.strip() or
                len(instructions) > 2048 or type(timeout) not in (int, float) or
                not math.isfinite(timeout) or not 0 < timeout <= 30):
            return None
        payload = {'model': model, 'state': state,
                   'questions': {'decision': {'type': 'noul', 'instructions': instructions}}}
        data = json.dumps(payload, allow_nan=False).encode('utf-8')
        if len(data) > 16384:
            return None
        request = urllib.request.Request('https://openrouter.ai/api/alpha/decisions',
            data=data, headers={'Content-Type': 'application/json'}, method='POST')
        # Never forward credentials to a redirect destination.
        request.add_unredirected_header('Authorization', 'Bearer ' + key)
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read(65537)
        if len(raw) > 65536:
            return None
        answer = json.loads(raw)['answers']['decision']
        value = answer['noul']
        if (answer['type'] != 'noul' or type(value) not in (float, int) or
                not math.isfinite(value) or not 0 <= value <= 1):
            return None
        return float(value)
    except Exception:
        # Upstream error bodies and exceptions may contain sensitive information.
        return None
