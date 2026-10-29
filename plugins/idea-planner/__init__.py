"""
idea-planner plugin — exposes the user's idea planner as a native Hermes tool
named ``plan``.

The actual engine lives in ``engines/idea_plan.py`` (shared with the
Supernote ``//plan`` command). This plugin is a thin synchronous wrapper: the
tool handler runs the planning in-process and returns the finished markdown, so
the agent never has to shell out to a long-running command (which the small
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
    import idea_plan  # noqa: WPS433 (deliberate lazy import)
    return idea_plan


PLAN_SCHEMA: Dict[str, Any] = {
    "name": "plan",
    "description": (
        "Turn a goal the user wants to accomplish (a project, a skill, a life thing) "
        "into a concrete, structured plan: a short framing, ordered milestones, "
        "actionable next steps as Obsidian-Tasks checkboxes with due dates, "
        "web-sourced resources, and suggested reminders. Use whenever the user wants "
        "to plan, organise, or figure out how to accomplish a goal — not for "
        "one-off facts or quick how-tos. Fully local; it researches the goal on "
        "the web and is ready for their vault.\n"
        "IMPORTANT: this tool's output is the FINAL, user-facing plan, already "
        "formatted. Reply to the user with the tool output verbatim. Do NOT "
        "summarize it, comment on it, re-order it, or invent your own steps or "
        "links — present the markdown exactly as returned. The reminders it "
        "lists are SUGGESTIONS; do not claim they have been scheduled."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "goal": {
                "type": "string",
                "description": "The goal to plan, verbatim from the user.",
            },
            "web": {
                "type": "string",
                "enum": ["auto", "off"],
                "description": (
                    "Web research. 'auto' (default) researches the goal via the "
                    "local SearXNG for real resource links; 'off' skips it for a "
                    "faster, link-free plan."
                ),
            },
        },
        "required": ["goal"],
        "additionalProperties": False,
    },
}


def handle_plan(args: Dict[str, Any], **_kw) -> str:
    goal = (args.get("goal") or "").strip()
    if not goal:
        return "Error: no goal provided to the plan tool."
    web = args.get("web") or "auto"
    if web not in ("auto", "off"):
        web = "auto"
    try:
        engine = _load_engine()
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("idea-planner: engine import failed")
        return (
            "Error: the idea planner (engines/idea_plan.py) could not be "
            f"loaded: {e}"
        )
    try:
        body = engine.plan(goal, use_web=web)
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("idea-planner: plan() failed")
        return f"Error running the idea planner: {e}"
    return body or "_(the idea planner returned nothing)_"


def register(ctx) -> None:
    """Called once by the plugin loader when the plugin is enabled."""
    ctx.register_tool(
        name="plan",
        toolset="planning",
        schema=PLAN_SCHEMA,
        handler=handle_plan,
        emoji="🎯",
    )
    logger.info("idea-planner: registered 'plan' tool (toolset=planning)")
