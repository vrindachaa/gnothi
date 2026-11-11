"""gnothi — epistemic self-check for Hermes.

Gives the agent three on-demand tools to test its own quantitative claims
against evidence and recognize when a conclusion goes beyond what the data
supports:

  verify_claim        — recompute a claim from supplied evidence
  evaluate_difference — is an observed difference statistically supported?
  qualify_conclusion   — the strongest conclusion the evidence actually permits

Pure Python stdlib. The three tools are deterministic and on-demand. Optional
automatic checking and Jev advisory support are disabled by default.
"""

from __future__ import annotations

from pathlib import Path

from . import schemas, tools

_SKILL_PATH = Path(__file__).parent / "skills" / "gnothi" / "SKILL.md"


def register(ctx) -> None:
    ctx.register_tool(name="verify_claim", toolset="gnothi",
                      schema=schemas.VERIFY_CLAIM, handler=tools.verify_claim)
    ctx.register_tool(name="evaluate_difference", toolset="gnothi",
                      schema=schemas.EVALUATE_DIFFERENCE, handler=tools.evaluate_difference)
    ctx.register_tool(name="qualify_conclusion", toolset="gnothi",
                      schema=schemas.QUALIFY_CONCLUSION, handler=tools.qualify_conclusion)
    get_config = getattr(ctx, "get_config", lambda key, default=None: default)
    if get_config("automatic_check", False) is True:
        from .auto_hook import DemoAudit
        from .jev import DEFAULT_MODEL
        audit = DemoAudit(
            remote=get_config("jev_remote", False),
            model=get_config("decision_model", DEFAULT_MODEL),
        )
        ctx.register_hook("post_tool_call", audit.observe)
        ctx.register_hook("transform_llm_output", audit.transform, hold_stream=True)
    ctx.register_skill(
        "gnothi", _SKILL_PATH,
        description="Know when to defer to gnothi before asserting a number or a conclusion.",
    )
