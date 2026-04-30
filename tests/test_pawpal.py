from datetime import date, time, timedelta
from unittest.mock import MagicMock, patch
import json

from pawpal_system import Owner, Pet, Scheduler, Task


# ── Original Scheduler Tests ────────────────────────────────────────

def test_task_mark_complete_sets_completed_true() -> None:
    task = Task(description="Test task", at=time(10, 0))
    assert task.completed is False
    next_task = task.mark_complete()
    assert task.completed is True
    assert next_task is None


def test_pet_add_task_increases_task_count() -> None:
    pet = Pet(pet_id="p1", name="Mochi", species="dog")
    start_count = len(pet.tasks)
    pet.add_task(Task(description="Walk", at=time(8, 0)))
    assert len(pet.tasks) == start_count + 1


def test_daily_task_completion_creates_next_day_task() -> None:
    today = date.today()
    pet = Pet(pet_id="p1", name="Mochi", species="dog")
    pet.add_task(Task(description="Morning walk", at=time(8, 0), due_date=today, frequency="daily"))

    did_complete = pet.mark_task_complete(description="Morning walk", at=time(8, 0), day=today)

    assert did_complete is True
    tomorrow = today + timedelta(days=1)
    tomorrow_tasks = pet.tasks_for_day(tomorrow)
    assert len(tomorrow_tasks) == 1
    assert tomorrow_tasks[0].description == "Morning walk"
    assert tomorrow_tasks[0].completed is False


def test_detect_conflicts_warns_for_same_time() -> None:
    owner = Owner(owner_name="Jordan")
    mochi = Pet(pet_id="p1", name="Mochi", species="dog")
    luna = Pet(pet_id="p2", name="Luna", species="cat")
    owner.add_pet(mochi)
    owner.add_pet(luna)
    today = date.today()

    mochi.add_task(Task(description="Walk", at=time(8, 0), due_date=today))
    luna.add_task(Task(description="Meds", at=time(8, 0), due_date=today))

    schedule, warnings = Scheduler().build_schedule(owner=owner, day=today)

    assert len(schedule) == 2
    assert any("Conflict at 08:00" in warning for warning in warnings)


def test_sorting_correctness_chronological() -> None:
    today = date.today()
    scheduler = Scheduler()

    tasks = [
        Task(description="B", at=time(9, 0), due_date=today),
        Task(description="A", at=time(8, 30), due_date=today),
        Task(description="C", at=time(9, 0), due_date=today),
    ]

    sorted_tasks = scheduler.sort_by_time(tasks)
    assert [t.description for t in sorted_tasks] == ["A", "B", "C"]


def test_no_tasks_returns_empty_schedule_and_no_warnings() -> None:
    owner = Owner(owner_name="Jordan")
    owner.add_pet(Pet(pet_id="p1", name="Mochi", species="dog"))
    scheduler = Scheduler()
    schedule, warnings = scheduler.build_schedule(owner=owner, day=date.today())

    assert schedule == []
    assert warnings == []


# ── Agent Tool Dispatch Tests ───────────────────────────────────────

def _make_owner_with_tasks() -> Owner:
    """Helper: owner with two pets and conflicting tasks."""
    owner = Owner(owner_name="Jordan")
    mochi = Pet(pet_id="p1", name="Mochi", species="dog")
    luna = Pet(pet_id="p2", name="Luna", species="cat")
    owner.add_pet(mochi)
    owner.add_pet(luna)
    today = date.today()
    mochi.add_task(Task(description="Morning walk", at=time(8, 0), due_date=today, frequency="daily"))
    luna.add_task(Task(description="Play time", at=time(8, 0), due_date=today, frequency="once"))
    mochi.add_task(Task(description="Dinner", at=time(18, 30), due_date=today, frequency="daily"))
    return owner


def test_agent_tool_get_schedule() -> None:
    from pawpal_agent import PawPalAgent
    owner = _make_owner_with_tasks()
    agent = PawPalAgent(owner, api_key="test-key")

    result = json.loads(agent._execute_tool("get_schedule", {}))
    assert len(result["schedule"]) == 3
    assert result["schedule"][0]["time"] == "08:00"
    assert len(result["warnings"]) > 0


def test_agent_tool_filter_tasks() -> None:
    from pawpal_agent import PawPalAgent
    owner = _make_owner_with_tasks()
    agent = PawPalAgent(owner, api_key="test-key")

    result = json.loads(agent._execute_tool("filter_tasks", {"pet_name": "Mochi"}))
    assert all(t["pet"] == "Mochi" for t in result["tasks"])
    assert len(result["tasks"]) == 2


def test_agent_tool_detect_conflicts() -> None:
    from pawpal_agent import PawPalAgent
    owner = _make_owner_with_tasks()
    agent = PawPalAgent(owner, api_key="test-key")

    result = json.loads(agent._execute_tool("detect_conflicts", {}))
    assert len(result["conflicts"]) >= 1
    assert "08:00" in result["conflicts"][0]


def test_agent_tool_get_pet_info() -> None:
    from pawpal_agent import PawPalAgent
    owner = _make_owner_with_tasks()
    agent = PawPalAgent(owner, api_key="test-key")

    result = json.loads(agent._execute_tool("get_pet_info", {}))
    assert len(result["pets"]) == 2
    names = [p["name"] for p in result["pets"]]
    assert "Mochi" in names
    assert "Luna" in names


def test_agent_tool_unknown_returns_error() -> None:
    from pawpal_agent import PawPalAgent
    owner = _make_owner_with_tasks()
    agent = PawPalAgent(owner, api_key="test-key")

    result = json.loads(agent._execute_tool("nonexistent_tool", {}))
    assert "error" in result


def test_agent_run_calls_tools_and_returns_plan() -> None:
    """Mock the Claude API to verify the agent loop processes tool calls correctly."""
    from pawpal_agent import PawPalAgent

    owner = _make_owner_with_tasks()
    agent = PawPalAgent(owner, api_key="test-key")

    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.name = "get_pet_info"
    tool_use_block.input = {}
    tool_use_block.id = "call_1"

    tool_response = MagicMock()
    tool_response.stop_reason = "tool_use"
    tool_response.content = [tool_use_block]

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Here is your care plan for today."

    final_response = MagicMock()
    final_response.stop_reason = "end_turn"
    final_response.content = [text_block]

    agent.client = MagicMock()
    agent.client.messages.create = MagicMock(side_effect=[tool_response, final_response])

    result = agent.run("Plan my day")

    assert result["plan"] == "Here is your care plan for today."
    assert result["step_count"] == 1
    assert result["steps"][0]["tool"] == "get_pet_info"
    assert agent.client.messages.create.call_count == 2


def test_agent_validate_plan_parses_valid_json() -> None:
    """Mock validation call to ensure JSON parsing works."""
    from pawpal_agent import PawPalAgent

    owner = _make_owner_with_tasks()
    agent = PawPalAgent(owner, api_key="test-key")

    mock_text = MagicMock()
    mock_text.text = '{"valid": true, "issues": [], "confidence": "High"}'

    mock_response = MagicMock()
    mock_response.content = [mock_text]

    agent.client = MagicMock()
    agent.client.messages.create = MagicMock(return_value=mock_response)

    plan_result = {"plan": "Test plan", "steps": [], "step_count": 0}
    validation = agent.validate_plan(plan_result)

    assert validation["valid"] is True
    assert validation["confidence"] == "High"
    assert validation["issues"] == []
