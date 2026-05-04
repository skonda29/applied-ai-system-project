import json
from datetime import date, time, timedelta
from unittest.mock import MagicMock, patch

import pytest

from pawpal_agent import PawPalAgent
from pawpal_system import Owner, Pet, Scheduler, Task


def test_task_mark_complete_sets_completed_true() -> None:
    task = Task(description="Test task", at=time(10, 0))
    assert task.completed is False
    next_task = task.mark_complete()
    assert task.completed is True
    assert next_task is None


def test_invalid_duration_raises_error() -> None:
    with pytest.raises(ValueError):
        Task(description="Bad task", at=time(9, 0), duration_minutes=0)


def test_daily_task_completion_creates_next_day_task() -> None:
    today = date.today()
    pet = Pet(pet_id="p1", name="Mochi", species="dog")
    pet.add_task(
        Task(
            description="Morning walk",
            at=time(8, 0),
            due_date=today,
            frequency="daily",
            duration_minutes=30,
        )
    )

    did_complete = pet.mark_task_complete(description="Morning walk", at=time(8, 0), day=today)

    assert did_complete is True
    tomorrow = today + timedelta(days=1)
    tomorrow_tasks = pet.tasks_for_day(tomorrow)
    assert len(tomorrow_tasks) == 1
    assert tomorrow_tasks[0].description == "Morning walk"
    assert tomorrow_tasks[0].completed is False
    assert tomorrow_tasks[0].duration_minutes == 30


def test_detect_conflicts_warns_for_same_time_and_overlap() -> None:
    owner = Owner(owner_name="Jordan")
    mochi = Pet(pet_id="p1", name="Mochi", species="dog")
    luna = Pet(pet_id="p2", name="Luna", species="cat")
    owner.add_pet(mochi)
    owner.add_pet(luna)
    today = date.today()

    mochi.add_task(Task(description="Walk", at=time(8, 0), due_date=today, duration_minutes=30))
    luna.add_task(Task(description="Meds", at=time(8, 0), due_date=today, duration_minutes=10))
    luna.add_task(Task(description="Breakfast", at=time(8, 20), due_date=today, duration_minutes=15))

    schedule, warnings = Scheduler().build_schedule(owner=owner, day=today)

    assert len(schedule) == 3
    assert any("Conflict at 08:00" in warning for warning in warnings)
    assert any("Overlap detected" in warning for warning in warnings)


def test_sorting_correctness_chronological() -> None:
    today = date.today()
    scheduler = Scheduler()

    tasks = [
        Task(description="B", at=time(9, 0), due_date=today),
        Task(description="A", at=time(8, 30), due_date=today),
        Task(description="C", at=time(9, 0), due_date=today),
    ]

    sorted_tasks = scheduler.sort_by_time(tasks)
    assert [task.description for task in sorted_tasks] == ["A", "B", "C"]


def test_agentic_plan_defers_low_priority_task_when_budget_is_tight() -> None:
    owner = Owner(owner_name="Jordan")
    pet = Pet(pet_id="p1", name="Mochi", species="dog")
    owner.add_pet(pet)
    today = date.today()

    pet.add_task(Task(description="Medication", at=time(8, 0), due_date=today, priority="critical", duration_minutes=10))
    pet.add_task(Task(description="Walk", at=time(8, 30), due_date=today, priority="high", duration_minutes=30))
    pet.add_task(Task(description="Brush coat", at=time(9, 15), due_date=today, priority="low", duration_minutes=30))

    result = Scheduler().generate_agentic_plan(owner=owner, day=today, available_minutes=40)

    assert [item["description"] for item in result.schedule] == ["Medication", "Walk"]
    assert len(result.deferred_tasks) == 1
    assert result.deferred_tasks[0]["description"] == "Brush coat"
    assert any("Deferred because" in warning for warning in result.warnings)


def test_agentic_plan_returns_trace_and_confidence() -> None:
    owner = Owner(owner_name="Jordan")
    pet = Pet(pet_id="p1", name="Mochi", species="dog")
    owner.add_pet(pet)
    today = date.today()

    pet.add_task(Task(description="Medication", at=time(8, 0), due_date=today, priority="critical", duration_minutes=10))
    pet.add_task(Task(description="Walk", at=time(8, 5), due_date=today, priority="high", duration_minutes=30))

    result = Scheduler().generate_agentic_plan(owner=owner, day=today, available_minutes=60)

    assert len(result.trace) >= 3
    assert result.confidence_score < 1.0
    assert any("Human review" in note for note in result.review_notes)


def test_no_tasks_returns_empty_schedule_and_no_warnings() -> None:
    owner = Owner(owner_name="Jordan")
    owner.add_pet(Pet(pet_id="p1", name="Mochi", species="dog"))

    result = Scheduler().generate_agentic_plan(owner=owner, day=date.today(), available_minutes=30)

    assert result.schedule == []
    assert result.warnings == []
    assert result.confidence_score == 1.0


# ---------------------------------------------------------------------------
# Agent tool dispatch tests
# ---------------------------------------------------------------------------

def _make_agent_owner() -> Owner:
    owner = Owner(owner_name="Jordan")
    mochi = Pet(pet_id="p1", name="Mochi", species="dog")
    luna = Pet(pet_id="p2", name="Luna", species="cat")
    owner.add_pet(mochi)
    owner.add_pet(luna)
    today = date.today()
    mochi.add_task(Task(description="Walk", at=time(8, 0), due_date=today, duration_minutes=30, priority="high"))
    luna.add_task(Task(description="Meds", at=time(8, 15), due_date=today, duration_minutes=10, priority="critical"))
    return owner


def test_agent_tool_get_schedule() -> None:
    owner = _make_agent_owner()
    agent = PawPalAgent(owner, api_key="fake-key")
    result = json.loads(agent._execute_tool("get_schedule", {"day": date.today().isoformat()}))
    assert "schedule" in result
    assert len(result["schedule"]) == 2


def test_agent_tool_filter_tasks() -> None:
    owner = _make_agent_owner()
    agent = PawPalAgent(owner, api_key="fake-key")
    result = json.loads(agent._execute_tool("filter_tasks", {"pet_name": "Mochi", "day": date.today().isoformat()}))
    assert len(result["tasks"]) == 1
    assert result["tasks"][0]["pet"] == "Mochi"


def test_agent_tool_detect_conflicts() -> None:
    owner = _make_agent_owner()
    agent = PawPalAgent(owner, api_key="fake-key")
    result = json.loads(agent._execute_tool("detect_conflicts", {"day": date.today().isoformat()}))
    assert "conflicts" in result
    assert any("Overlap" in c for c in result["conflicts"])


def test_agent_tool_get_pet_info() -> None:
    owner = _make_agent_owner()
    agent = PawPalAgent(owner, api_key="fake-key")
    result = json.loads(agent._execute_tool("get_pet_info", {}))
    assert len(result["pets"]) == 2
    names = {p["name"] for p in result["pets"]}
    assert names == {"Mochi", "Luna"}


def test_agent_tool_unknown_returns_error() -> None:
    owner = _make_agent_owner()
    agent = PawPalAgent(owner, api_key="fake-key")
    result = json.loads(agent._execute_tool("nonexistent_tool", {}))
    assert "error" in result


# ---------------------------------------------------------------------------
# Agent loop and validation tests (mocked Claude API)
# ---------------------------------------------------------------------------

def _mock_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


def _mock_tool_block(tool_id: str, name: str, input_data: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = input_data
    return block


def test_agent_run_with_mocked_claude() -> None:
    owner = _make_agent_owner()
    agent = PawPalAgent(owner, api_key="fake-key")

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [
        _mock_tool_block("call-1", "get_pet_info", {}),
        _mock_tool_block("call-2", "get_schedule", {"day": date.today().isoformat()}),
    ]

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [_mock_text_block("Here is your care plan for today.")]

    agent.client = MagicMock()
    agent.client.messages.create = MagicMock(side_effect=[tool_response, final_response])

    result = agent.run()

    assert result["step_count"] == 2
    assert "care plan" in result["plan"].lower()
    assert len(result["steps"]) == 2


def test_agent_validate_plan_parses_json() -> None:
    owner = _make_agent_owner()
    agent = PawPalAgent(owner, api_key="fake-key")

    mock_response = MagicMock()
    mock_response.content = [
        _mock_text_block('{"valid": true, "issues": [], "confidence": "High"}')
    ]

    agent.client = MagicMock()
    agent.client.messages.create = MagicMock(return_value=mock_response)

    plan_result = {"plan": "Sample plan text", "steps": [], "step_count": 0}
    validation = agent.validate_plan(plan_result)

    assert validation["valid"] is True
    assert validation["confidence"] == "High"
    assert validation["issues"] == []
