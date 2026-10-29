"""
learn-accelerator plugin — exposes the user's learning accelerator as a native
Hermes tool named ``learn``.

The actual engine lives in ``engines/learn_explain.py`` (shared with the
Supernote ``//learn`` command). This plugin is a thin synchronous wrapper: the
tool handler runs the explanation in-process and returns the finished markdown,
so the agent never has to shell out to a long-running command (which the small
local model tends to background and lose).
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

# The engine lives in engines/; make it importable.
_SCRIPTS_DIR = os.environ.get("MYOS_ENGINES", str(Path(__file__).resolve().parents[2] / "engines"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _load_engine():
    """Import the shared engine lazily so a bad import can't break plugin load."""
    import learn_explain  # noqa: WPS433 (deliberate lazy import)
    return learn_explain


LEARN_SCHEMA: Dict[str, Any] = {
    "name": "learn",
    "description": (
        "Explain a math problem, word problem, or programming/C++ concept in "
        "the user's personal study style so it sticks: answer/solution first, a "
        "numbered step-by-step, a memory trick (mnemonic/analogy), and a short "
        "worked-example or gotcha. Use whenever the user wants to understand, learn, "
        "study, or solve a math or programming topic (not just a one-line fact). "
        "Fully local; it auto fact-checks concepts against the web and is already "
        "personalised from the user's own notes.\n"
        "IMPORTANT: this tool's output is the FINAL, user-facing answer, already "
        "written in the user's style. Reply to the user with the tool output verbatim. Do "
        "NOT summarize it, comment on it, describe it, or add your own explanation "
        "— just present the markdown exactly as returned."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The question or problem to explain, verbatim from the user.",
            },
            "web": {
                "type": "string",
                "enum": ["auto", "on", "off"],
                "description": (
                    "Web grounding. 'auto' (default): fact-check concepts, skip "
                    "bare arithmetic. 'off' for the fastest answer; 'on' to force it."
                ),
            },
        },
        "required": ["topic"],
        "additionalProperties": False,
    },
}


def handle_learn(args: Dict[str, Any], **_kw) -> str:
    topic = (args.get("topic") or "").strip()
    if not topic:
        return "Error: no topic provided to the learn tool."
    web = args.get("web") or "auto"
    if web not in ("auto", "on", "off"):
        web = "auto"
    try:
        engine = _load_engine()
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("learn-accelerator: engine import failed")
        return (
            "Error: the learning engine (engines/learn_explain.py) could not "
            f"be loaded: {e}"
        )
    try:
        body = engine.explain(topic, use_web=web)
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("learn-accelerator: explain() failed")
        return f"Error running the learning accelerator: {e}"
    return body or "_(the learning engine returned nothing)_"


def register(ctx) -> None:
    """Called once by the plugin loader when the plugin is enabled."""
    ctx.register_tool(
        name="learn",
        toolset="learning",
        schema=LEARN_SCHEMA,
        handler=handle_learn,
        emoji="📚",
    )
    logger.info("learn-accelerator: registered 'learn' tool (toolset=learning)")
