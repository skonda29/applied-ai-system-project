"""PawPal+ AI Agent — multi-step scheduling agent powered by Claude.

The agent uses the existing Scheduler as its toolset: it can retrieve
today's tasks, detect conflicts, filter by pet, and mark tasks complete.
Claude reasons through the schedule step-by-step and produces a
natural-language care plan with explanations. A self-check guardrail
validates the final plan before returning it.
"""

from __future__ import annotations

import json
import os
from datetime import date, time
from typing import Any

from anthropic import Anthropic

from pawpal_system import Owner, Pet, Scheduler, Task

TOOLS = [
    {
        "name": "get_schedule",
        "description": (
            "Retrieve today's schedule for the owner. Returns a list of scheduled items "
            "(time, pet_name, description, frequency) and any conflict warnings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "day": {
                    "type": "string",
                    "description": "ISO date string (YYYY-MM-DD). Defaults to today.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "filter_tasks",
        "description": (
            "Filter tasks by pet name and/or completion status for a given day. "
            "Useful for focusing on one pet or seeing only incomplete tasks."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "day": {"type": "string", "description": "ISO date (YYYY-MM-DD). Defaults to today."},
                "pet_name": {"type": "string", "description": "Filter to this pet only."},
                "completed": {"type": "boolean", "description": "Filter by completion status."},
            },
            "required": [],
        },
    },
    {
        "name": "detect_conflicts",
        "description": (
            "Check a day's schedule for time conflicts. Returns a list of warning strings."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "day": {"type": "string", "description": "ISO date (YYYY-MM-DD). Defaults to today."},
            },
            "required": [],
        },
    },
    {
        "name": "get_pet_info",
        "description": "Get information about all pets and their task counts.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
]

SYSTEM_PROMPT = """\
You are PawPal+ AI, a pet care scheduling assistant. You help pet owners
plan their daily care routines by analyzing their tasks, detecting conflicts,
and producing a clear, prioritized care plan.

You have access to tools that let you inspect the owner's schedule. Use them
step-by-step:
1. First, get an overview of the pets.
2. Retrieve today's full schedule.
3. Check for conflicts.
4. If there are conflicts, filter tasks per pet to understand them.
5. Produce a final care plan that:
   - Lists tasks in chronological order
   - Flags any conflicts with suggested resolutions
   - Explains WHY certain orderings or adjustments matter for pet wellbeing
   - Notes recurring vs one-time tasks

Be concise but thorough. After producing the plan, review it yourself:
verify no tasks are missing, conflicts are addressed, and times are correct.
State your confidence level at the end (High / Medium / Low).
"""


def _parse_date(s: str | None) -> date:
    if s:
        return date.fromisoformat(s)
    return date.today()


class PawPalAgent:
    """Multi-step agent that uses Claude + Scheduler tools to build care plans."""

    def __init__(self, owner: Owner, *, api_key: str | None = None, model: str = "claude-sonnet-4-20250514"):
        self.owner = owner
        self.scheduler = Scheduler()
        self.model = model
        self.client = Anthropic(api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.steps: list[dict[str, Any]] = []

    def _execute_tool(self, name: str, input_data: dict) -> str:
        """Dispatch a tool call to the Scheduler and return JSON result."""
        if name == "get_schedule":
            day = _parse_date(input_data.get("day"))
            items, warnings = self.scheduler.build_schedule(owner=self.owner, day=day)
            return json.dumps({
                "schedule": [
                    {
                        "time": it["time"].strftime("%H:%M"),
                        "pet": it["pet_name"],
                        "species": it["species"],
                        "task": it["description"],
                        "frequency": it["frequency"],
                    }
                    for it in items
                ],
                "warnings": warnings,
                "date": day.isoformat(),
            })

        if name == "filter_tasks":
            day = _parse_date(input_data.get("day"))
            pairs = self.scheduler.filter_tasks(
                owner=self.owner,
                day=day,
                pet_name=input_data.get("pet_name"),
                completed=input_data.get("completed"),
            )
            return json.dumps({
                "tasks": [
                    {
                        "pet": p.name,
                        "task": t.description,
                        "time": t.at.strftime("%H:%M"),
                        "frequency": t.frequency,
                        "completed": t.completed,
                    }
                    for p, t in pairs
                ],
                "date": day.isoformat(),
            })

        if name == "detect_conflicts":
            day = _parse_date(input_data.get("day"))
            items, _ = self.scheduler.build_schedule(owner=self.owner, day=day)
            warnings = self.scheduler.detect_conflicts(items)
            return json.dumps({"conflicts": warnings, "date": day.isoformat()})

        if name == "get_pet_info":
            return json.dumps({
                "pets": [
                    {
                        "name": p.name,
                        "species": p.species,
                        "total_tasks": len(p.tasks),
                        "tasks_today": len(p.tasks_for_day(date.today())),
                    }
                    for p in self.owner.pets
                ],
                "owner": self.owner.owner_name,
            })

        return json.dumps({"error": f"Unknown tool: {name}"})

    def run(self, user_request: str | None = None) -> dict[str, Any]:
        """Run the agent loop: send messages, handle tool calls, return final plan."""
        if user_request is None:
            user_request = "Please build today's care plan for all my pets."

        messages: list[dict] = [{"role": "user", "content": user_request}]
        self.steps = []

        while True:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=SYSTEM_PROMPT,
                tools=TOOLS,
                messages=messages,
            )

            if response.stop_reason == "tool_use":
                tool_results = []
                assistant_content = response.content
                for block in response.content:
                    if block.type == "tool_use":
                        result = self._execute_tool(block.name, block.input)
                        self.steps.append({
                            "tool": block.name,
                            "input": block.input,
                            "output": json.loads(result),
                        })
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        })

                messages.append({"role": "assistant", "content": assistant_content})
                messages.append({"role": "user", "content": tool_results})
                continue

            final_text = ""
            for block in response.content:
                if hasattr(block, "text"):
                    final_text += block.text

            return {
                "plan": final_text,
                "steps": self.steps,
                "step_count": len(self.steps),
            }

    def validate_plan(self, plan_result: dict[str, Any]) -> dict[str, Any]:
        """Self-check guardrail: ask Claude to verify its own plan against the raw schedule."""
        items, warnings = self.scheduler.build_schedule(owner=self.owner)
        raw_schedule = self.scheduler.format_schedule(items)

        response = self.client.messages.create(
            model=self.model,
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "You are a QA checker for a pet care scheduling system.\n\n"
                        f"RAW SCHEDULE (ground truth):\n{raw_schedule}\n\n"
                        f"CONFLICTS DETECTED: {warnings}\n\n"
                        f"AI-GENERATED PLAN:\n{plan_result['plan']}\n\n"
                        "Verify:\n"
                        "1. Are all tasks from the raw schedule present in the plan?\n"
                        "2. Are the times correct?\n"
                        "3. Are conflicts mentioned and addressed?\n"
                        "4. Is the advice reasonable for pet care?\n\n"
                        "Respond with a JSON object: "
                        '{"valid": true/false, "issues": ["list of issues or empty"], '
                        '"confidence": "High/Medium/Low"}'
                    ),
                }
            ],
        )

        text = response.content[0].text
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            validation = json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            validation = {"valid": False, "issues": ["Could not parse validation response"], "confidence": "Low"}

        return validation
