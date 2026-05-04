import logging
import os
from datetime import date, time, timedelta

from pawpal_system import Owner, Pet, PlannerResult, Scheduler, Task


def print_plan(result: PlannerResult, scheduler: Scheduler) -> None:
    print("Agentic Daily Plan")
    print("-" * 18)
    print(scheduler.format_schedule(result.schedule))
    print(f"\nConfidence: {result.confidence_score:.2f}")

    if result.warnings:
        print("\nWarnings")
        print("-" * 8)
        for warning in result.warnings:
            print(f"- {warning}")

    print("\nExecution Trace")
    print("-" * 15)
    for step in result.trace:
        print(f"- {step}")

    print("\nHuman Review")
    print("-" * 12)
    for note in result.review_notes:
        print(f"- {note}")


def build_demo_owner() -> Owner:
    """Create a sample owner with pets and tasks for demonstration."""
    owner = Owner(owner_name="Jordan")

    mochi = Pet(pet_id="pet-1", name="Mochi", species="dog")
    luna = Pet(pet_id="pet-2", name="Luna", species="cat")
    owner.add_pet(mochi)
    owner.add_pet(luna)

    today = date.today()

    mochi.add_task(
        Task(
            description="Morning walk",
            at=time(8, 0),
            due_date=today,
            frequency="daily",
            duration_minutes=30,
            priority="high",
        )
    )
    luna.add_task(
        Task(
            description="Medication",
            at=time(8, 15),
            due_date=today,
            frequency="daily",
            duration_minutes=10,
            priority="critical",
        )
    )
    mochi.add_task(
        Task(
            description="Dinner",
            at=time(18, 30),
            due_date=today,
            frequency="daily",
            duration_minutes=20,
            priority="high",
        )
    )
    luna.add_task(
        Task(
            description="Play time",
            at=time(19, 0),
            due_date=today,
            frequency="once",
            duration_minutes=25,
            priority="medium",
        )
    )
    return owner


def run_deterministic_demo(owner: Owner) -> None:
    """Run the rule-based scheduler demo."""
    today = date.today()
    scheduler = Scheduler()

    print("=" * 50)
    print("PART 1: Rule-Based Scheduler")
    print("=" * 50)

    result = scheduler.generate_agentic_plan(owner=owner, day=today, available_minutes=60)
    print_plan(result, scheduler)

    print("\nRecurring demo")
    print("-" * 14)
    mochi = owner.find_pet_by_name("Mochi")
    did_complete = mochi.mark_task_complete(description="Morning walk", at=time(8, 0), day=today)
    print(f"Marked complete? {did_complete}")
    tomorrow = today + timedelta(days=1)
    tomorrow_pairs = scheduler.filter_tasks(owner=owner, day=tomorrow, pet_name="Mochi", completed=False)
    if tomorrow_pairs:
        print("Tomorrow's newly generated tasks for Mochi:")
        for task in scheduler.sort_by_time([task for (_pet, task) in tomorrow_pairs]):
            print(
                f"- {task.due_date.isoformat()} {task.at.strftime('%H:%M')} "
                f"{task.description} ({task.frequency})"
            )
    else:
        print("No recurring tasks were generated for tomorrow.")


def run_agent_demo(owner: Owner) -> None:
    """Run the Claude-powered AI agent demo with observable intermediate steps."""
    from pawpal_agent import PawPalAgent

    print("\n" + "=" * 50)
    print("PART 2: Claude AI Agent (Multi-Step Tool-Calling)")
    print("=" * 50)

    agent = PawPalAgent(owner)
    plan_result = agent.run("Please build today's care plan for all my pets.")

    print("\n--- Agent Intermediate Steps ---")
    for i, step in enumerate(plan_result["steps"], 1):
        print(f"\nStep {i}: tool={step['tool']}")
        print(f"  Input:  {step['input']}")
        output_preview = str(step["output"])
        if len(output_preview) > 200:
            output_preview = output_preview[:200] + "..."
        print(f"  Output: {output_preview}")

    print(f"\nTotal tool calls: {plan_result['step_count']}")

    print("\n--- AI-Generated Care Plan ---")
    print(plan_result["plan"])

    print("\n--- Self-Check Validation ---")
    validation = agent.validate_plan(plan_result)
    print(f"Valid: {validation.get('valid')}")
    print(f"Confidence: {validation.get('confidence')}")
    if validation.get("issues"):
        print("Issues:")
        for issue in validation["issues"]:
            print(f"  - {issue}")
    else:
        print("No issues found.")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

    owner = build_demo_owner()
    run_deterministic_demo(owner)

    if os.environ.get("ANTHROPIC_API_KEY"):
        owner_fresh = build_demo_owner()
        run_agent_demo(owner_fresh)
    else:
        print("\n" + "=" * 50)
        print("PART 2: Claude AI Agent (skipped)")
        print("=" * 50)
        print("Set ANTHROPIC_API_KEY to enable the AI agent demo.")
        print("Example: ANTHROPIC_API_KEY=sk-... python main.py")


if __name__ == "__main__":
    main()
