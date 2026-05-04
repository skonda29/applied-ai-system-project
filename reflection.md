# PawPal+ Reflection

## Original Project

PawPal+ began as a pet care scheduling assistant for a busy owner managing daily routines across multiple pets. The original version focused on representing owners, pets, and tasks, sorting tasks by time, detecting simple conflicts, and supporting recurring care items.

## What Changed

The strongest improvement in this version is that the system now has two planning layers. The deterministic rule-based scheduler collects eligible tasks, builds a plan within a time budget, checks for conflicts and overlaps, produces a confidence score, and asks for human review when the plan has warnings or deferred work. On top of that, a Claude-powered AI agent (`pawpal_agent.py`) reasons through the schedule using multi-step tool-calling, generates a natural-language care plan with explanations, and validates its own output through a self-check guardrail. Both layers share the same `Scheduler` backend, so there is one source of truth for scheduling logic.

## Reliability Summary

- 15 out of 15 automated tests passed.
- Core scheduler tests (8): recurrence rollover, sorting, invalid-input rejection, budget-aware deferral, overlap/conflict detection, confidence scoring, and empty-state handling.
- Agent tool dispatch tests (5): `get_schedule`, `filter_tasks`, `detect_conflicts`, `get_pet_info`, and unknown-tool error handling.
- Agent loop and validation tests (2): mocked Claude API for the multi-step agent loop and JSON parsing in `validate_plan`.
- The most important lesson was that schedule validation matters as much as schedule generation, and the AI agent's self-check guardrail adds a second layer of verification.

## Limitations and Biases

The planner is only as good as the priorities, durations, and times entered by the user. It does not understand deeper medical urgency or complex context such as travel time, emergencies, or uncertain task lengths. The Claude AI agent adds natural-language reasoning but its output may vary between runs due to LLM non-determinism. The self-check guardrail mitigates this by cross-referencing the AI plan against the raw schedule.

## Misuse Risk

This project could be misused if someone treated it like a fully autonomous pet-health authority. To reduce that risk, it surfaces warnings, confidence scores, and human review notes instead of pretending the plan is always safe. The AI agent is read-only by design -- it can observe the schedule through tools but cannot modify the underlying data model, preventing unintended automated changes to care routines.

## AI Collaboration

One helpful AI suggestion was to structure the agent's tool definitions as JSON schemas that map directly to existing Scheduler methods. This made the integration clean -- each tool call dispatches to a real Python method rather than requiring new logic. It also made testing straightforward since tool dispatch could be unit-tested without mocking the LLM.

One flawed AI suggestion was to have the agent directly manipulate the schedule (reorder tasks, move times) as part of its reasoning. This would have introduced a mutable state problem where the agent's "suggestions" silently alter the owner's actual data. I rejected this and kept the agent read-only, which is critical for trustworthiness.
