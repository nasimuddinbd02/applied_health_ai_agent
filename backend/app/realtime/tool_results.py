"""Lift structured facts out of the agent's tool output, server-side.

Before the renovation the browser regex-scraped ``"patient_id": N`` out of the
transcript it was sent, and believed it. That is the client asserting identity
(design doc §16) and it leaks whatever a tool happened to return. Now the
server reads its own tools' output here and tells the client only the
conclusion.
"""

import json
from typing import Any

# Tools whose result identifies the person we are talking to.
_IDENTITY_TOOLS = ("register_patient", "find_patient_by_name", "get_patient")
_AVAILABILITY_TOOLS = ("get_availability",)


def _decode(content: Any) -> Any:
    """MCP tool output arrives as JSON text, sometimes double-encoded."""
    if isinstance(content, (dict, list)):
        return content
    if not isinstance(content, str):
        return None
    text = content.strip()
    if not text:
        return None
    for _ in range(2):
        try:
            text = json.loads(text)
        except (json.JSONDecodeError, TypeError):
            return text if isinstance(text, (dict, list)) else None
        if isinstance(text, (dict, list)):
            # A list of MCP content blocks: unwrap the text payload and retry.
            if isinstance(text, list) and text and isinstance(text[0], dict) and "text" in text[0]:
                text = text[0]["text"]
                continue
            return text
    return None


class ToolResultReader:
    """Reads the agent's tool results for facts the realtime layer can use."""

    def identity(self, tool_results: list[dict]) -> dict | None:
        """The patient the agent resolved, if exactly one is unambiguous.

        A name lookup that returns two people is *not* an identification — the
        agent has to disambiguate in conversation first.
        """
        for result in reversed(tool_results):
            if result.get("tool") not in _IDENTITY_TOOLS:
                continue
            data = _decode(result.get("content"))
            record = None
            if isinstance(data, dict) and "patient_id" in data:
                record = data
            elif isinstance(data, list) and len(data) == 1 and isinstance(data[0], dict):
                record = data[0] if "patient_id" in data[0] else None
            if not record:
                continue
            try:
                patient_id = int(record["patient_id"])
            except (TypeError, ValueError):
                continue
            return {"patient_id": patient_id, "name": str(record.get("name") or "")}
        return None

    def appointment_options(self, tool_results: list[dict], *, limit: int = 6) -> list[dict]:
        """Open slots the agent looked at, as selectable options for the UI."""
        for result in reversed(tool_results):
            if result.get("tool") not in _AVAILABILITY_TOOLS:
                continue
            data = _decode(result.get("content"))
            if not isinstance(data, list):
                continue
            options = []
            for slot in data[:limit]:
                if not isinstance(slot, dict) or "slot_id" not in slot:
                    continue
                options.append({
                    "id": f"slot-{slot['slot_id']}",
                    "slot_id": slot["slot_id"],
                    "doctor_id": slot.get("doctor_id"),
                    "start": slot.get("starts_at"),
                    "duration_min": slot.get("duration_min"),
                })
            if options:
                return options
        return []

    def booked_appointment(self, tool_results: list[dict]) -> dict | None:
        for result in reversed(tool_results):
            if result.get("tool") != "book_appointment":
                continue
            data = _decode(result.get("content"))
            if isinstance(data, dict) and "appointment_id" in data:
                return data
        return None
