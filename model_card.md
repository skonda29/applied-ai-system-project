# PawPal+ Model Card

## Model Overview

PawPal+ uses **Claude (claude-sonnet-4-20250514)** via the Anthropic API as a multi-step reasoning agent for pet care scheduling. The agent does not generate schedules from scratch — it calls deterministic scheduling tools (sort, filter, conflict detection) and then synthesizes the results into a natural-language care plan with explanations.

## Intended Use

- **Primary users**: Pet owners managing daily care routines for one or more pets.
- **Use case**: Generating explained, conflict-aware daily care plans from structured task data.
- **Not intended for**: Medical or veterinary advice, emergency care decisions, or unsupervised automated pet care.

## AI Collaboration During Development

### Helpful AI Suggestion

Copilot Chat suggested structuring the agent's tool definitions as a JSON schema that maps directly to existing Scheduler methods. This made the integration clean — each tool call dispatches to a real Python method rather than requiring new logic. It also made testing straightforward since tool dispatch could be unit-tested without mocking the LLM.

### Flawed AI Suggestion

An early AI suggestion was to have the agent directly manipulate the schedule (reorder tasks, move times) as part of its reasoning. This would have introduced a mutable state problem — the agent's "suggestions" would silently alter the owner's actual data. I rejected this and kept the agent read-only: it observes the schedule through tools and produces advice, but never mutates the underlying data model. This separation is critical for trustworthiness.

## Limitations and Biases

- **Schedule complexity**: Conflict detection uses exact-time matching only, not duration-based overlap. Two 30-minute tasks at 8:00 and 8:15 would not be flagged as conflicting.
- **Species bias**: The system treats all pets equally in scheduling. It does not account for species-specific care patterns (e.g., dogs needing outdoor time, cats being more independent).
- **Language bias**: The agent responds in English only and may not handle non-English pet names or task descriptions well.
- **Single-owner scope**: The system assumes one owner. Multi-household or shared pet custody scenarios are not modeled.
- **LLM variability**: Claude's natural-language plan may vary between runs. The self-check guardrail mitigates this but cannot guarantee identical outputs for identical inputs.

## Misuse Potential and Prevention

- **Over-reliance risk**: Users might treat the AI-generated plan as authoritative veterinary or medical guidance. The system includes a disclaimer that it is a scheduling tool, not a medical advisor.
- **Data privacy**: Pet/owner data is sent to the Anthropic API for processing. Users should not enter sensitive personal information beyond what is needed for scheduling.
- **Automation risk**: The agent is read-only by design — it cannot mark tasks complete, modify schedules, or take actions on behalf of the user. This prevents unintended automated changes to care routines.
- **Guardrails in place**:
  - Self-check validation verifies the plan against ground-truth schedule data.
  - The agent's system prompt constrains it to scheduling advice only.
  - Tool dispatch only exposes read operations — no write/delete tools exist.

## Testing and Reliability

### Test Results

**13 out of 13 tests passed** across three categories:

| Category | Tests | Result |
|---|---|---|
| Core Scheduler (sorting, filtering, conflicts, recurrence) | 6 | 6/6 passed |
| Agent Tool Dispatch (get_schedule, filter_tasks, detect_conflicts, get_pet_info) | 5 | 5/5 passed |
| Agent Loop & Validation (mocked Claude API, JSON parsing) | 2 | 2/2 passed |

### Reliability Mechanisms

1. **Self-check guardrail**: A second Claude call cross-references the AI plan against the raw schedule to verify completeness, time accuracy, and conflict coverage. Returns a confidence score (High/Medium/Low).
2. **Observable intermediate steps**: Every tool call the agent makes is recorded with its input and output, enabling debugging and transparency.
3. **Deterministic fallback**: The rule-based Scheduler works independently of the AI agent, so the system remains functional even without an API key.

### What Surprised Me During Testing

The agent sometimes reordered its tool calls in unexpected ways — occasionally calling `detect_conflicts` before `get_schedule`, or calling `filter_tasks` multiple times for different pets. Despite the non-deterministic ordering, the final plans were consistently accurate because each tool returns the same ground-truth data regardless of call order. This reinforced that the tool-based architecture is resilient to LLM reasoning variability.

## Evaluation Metrics

- **Functional correctness**: 13/13 automated tests pass.
- **Plan completeness**: Self-check guardrail verifies all tasks appear in the final plan.
- **Conflict detection accuracy**: 100% for exact-time conflicts in test cases.
- **Confidence scores**: Validation typically returns "High" confidence when all tasks and conflicts are properly addressed.

## Future Improvements

- Add duration-based overlap detection for more realistic conflict analysis.
- Support species-specific scheduling heuristics (e.g., outdoor time for dogs).
- Add multi-language support for task descriptions.
- Implement a feedback loop where users can rate plans to improve future suggestions.
- Add structured logging for production-level observability.
