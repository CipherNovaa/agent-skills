"""
reminders plugin — set / list / cancel real scheduled reminders that ping the user
on Discord, backed by `hermes cron`.

The engine lives in ``engines/reminder_set.py``. It builds each reminder as a
cron "no-agent script" job: a tiny generated script prints the reminder text and
cron delivers that stdout verbatim — so when a reminder fires, no LLM runs and
the exact text is what the user receives.

This is the actuator behind the idea-planner's "⏰ Suggested reminders": the
planner proposes them; ``set_reminder`` turns a chosen one into a real job.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)

_SCRIPTS_DIR = os.environ.get("MYOS_ENGINES", str(Path(__file__).resolve().parents[2] / "engines"))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)


def _engine():
    import reminder_set  # noqa: WPS433 (deliberate lazy import)
    return reminder_set


SET_SCHEMA: Dict[str, Any] = {
    "name": "set_reminder",
    "description": (
        "Schedule a real reminder that pings the user on Discord at a chosen time. "
        "Use when the user asks to be reminded of something, or to act on a "
        "suggested reminder from a plan. Confirm the time back to them using the "
        "tool's returned 'Next fires' value, and mention they can cancel it.\n"
        "The `schedule` must be one of: a relative offset like '30m', '2h', or "
        "'1d' (fires once that far from now); or a 5-field cron expression "
        "(minute hour day-of-month month day-of-week), e.g. '0 9 * * *' = 9am "
        "daily, '0 10 * * 1' = 10am every Monday, '0 9 10 6 *' = 9am on June 10. "
        "For a specific one-off date/time use a cron expression with "
        "recurring=false. Set recurring=true ONLY for genuinely repeating "
        "reminders. Convert the user's natural phrasing into the right schedule "
        "yourself; today's date and clock are correct on this machine."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "The reminder message, in the user's words. Sent verbatim.",
            },
            "schedule": {
                "type": "string",
                "description": "Relative ('2h','1d') or 5-field cron ('0 9 * * *').",
            },
            "recurring": {
                "type": "boolean",
                "description": "True only for repeating reminders. Default false (one-shot).",
            },
        },
        "required": ["text", "schedule"],
        "additionalProperties": False,
    },
}

LIST_SCHEMA: Dict[str, Any] = {
    "name": "list_reminders",
    "description": (
        "List the currently scheduled reminders / cron jobs (name and next run "
        "time). Use when the user asks what reminders they have set."
    ),
    "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
}

CANCEL_SCHEMA: Dict[str, Any] = {
    "name": "cancel_reminder",
    "description": (
        "Cancel a scheduled reminder by its name (preferred, e.g. "
        "'reminder-weekly-review-a1b2') or job id. Use list_reminders first if "
        "you don't have the exact name."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "ref": {
                "type": "string",
                "description": "The reminder name (or job id) to cancel.",
            },
        },
        "required": ["ref"],
        "additionalProperties": False,
    },
}


def handle_set(args: Dict[str, Any], **_kw) -> str:
    text = (args.get("text") or "").strip()
    schedule = (args.get("schedule") or "").strip()
    recurring = bool(args.get("recurring") or False)
    if not text or not schedule:
        return "Error: set_reminder needs both 'text' and 'schedule'."
    try:
        return _engine().make_reminder(text, schedule, recurring=recurring)
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("reminders: make_reminder failed")
        return f"Error setting reminder: {e}"


def handle_list(args: Dict[str, Any], **_kw) -> str:
    try:
        return _engine().list_reminders()
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("reminders: list_reminders failed")
        return f"Error listing reminders: {e}"


def handle_cancel(args: Dict[str, Any], **_kw) -> str:
    ref = (args.get("ref") or "").strip()
    if not ref:
        return "Error: cancel_reminder needs a reminder name or id."
    try:
        return _engine().cancel_reminder(ref)
    except Exception as e:  # pragma: no cover — defensive
        logger.exception("reminders: cancel_reminder failed")
        return f"Error cancelling reminder: {e}"


def register(ctx) -> None:
    """Called once by the plugin loader when the plugin is enabled."""
    ctx.register_tool(name="set_reminder", toolset="reminders",
                      schema=SET_SCHEMA, handler=handle_set, emoji="⏰")
    ctx.register_tool(name="list_reminders", toolset="reminders",
                      schema=LIST_SCHEMA, handler=handle_list, emoji="📋")
    ctx.register_tool(name="cancel_reminder", toolset="reminders",
                      schema=CANCEL_SCHEMA, handler=handle_cancel, emoji="🗑️")
    logger.info("reminders: registered set_reminder + list_reminders + "
                "cancel_reminder (toolset=reminders)")
