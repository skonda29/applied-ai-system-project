"""PawPal+ CLI demo — shows both the deterministic scheduler and the AI agent."""

from datetime import date, time, timedelta

from pawpal_system import Owner, Pet, Scheduler, Task


def build_demo_owner() -> Owner:
    """Create a sample owner with pets and tasks for demonstration."""
    owner = Owner(owner_name="Jordan")

    mochi = Pet(pet_id="pet-1", name="Mochi", species="dog")
    luna = Pet(pet_id="pet-2", name="Luna", species="cat")

    owner.add_pet(mochi)
    owner.add_pet(luna)

    today = date.today()

    mochi.add_task(Task(description="Dinner", at=time(18, 30), due_date=today, frequency="daily"))
    luna.add_task(Task(description="Meds", at=time(9, 15), due_date=today, frequency="daily"))
    mochi.add_task(Task(description="Morning walk", at=time(8, 0), due_date=today, frequency="daily"))
    luna.add_task(Task(description="Play time", at=time(8, 0), due_date=today, frequency="once"))
    mochi.add_task(Task(description="Grooming", at=time(14, 0), due_date=today, frequency="weekly"))
    luna.add_task(Task(description="Vet checkup", at=time(14, 0), due_date=today, frequency="once"))

    return owner


def run_scheduler_demo(owner: Owner) -> None:
    """Run the original deterministic scheduler demo."""
    print("=" * 60)
    print("PART 1: Deterministic Scheduler")
    print("=" * 60)

    scheduler = Scheduler()
    today = date.today()
    schedule, warnings = scheduler.build_schedule(owner=owner, day=today)

    print("\nToday's Schedule")
    print("-" * 16)
    print(scheduler.format_schedule(schedule))
    if warnings:
        print("\nWarnings")
        print("-" * 8)
        for w in warnings:
            print(f"  - {w}")

    print("\nFiltered (Mochi, incomplete)")
    print("-" * 26)
    mochi_pairs = scheduler.filter_tasks(owner=owner, day=today, pet_name="Mochi", completed=False)
    mochi_only_schedule = [
        {
            "time": t.at,
            "date": t.due_date,
            "pet_name": p.name,
            "pet_id": p.pet_id,
            "species": p.species,
            "description": t.description,
            "frequency": t.frequency,
            "completed": t.completed,
        }
        for (p, t) in mochi_pairs
    ]
    mochi_only_schedule.sort(key=lambda x: (x["time"], x["description"]))
    print(scheduler.format_schedule(mochi_only_schedule))

    print("\nRecurring demo")
    print("-" * 14)
    mochi = owner.find_pet_by_name("Mochi")
    did_complete = mochi.mark_task_complete(description="Morning walk", at=time(8, 0), day=today)
    print(f"Marked complete? {did_complete}")
    tomorrow = today + timedelta(days=1)
    tomorrow_pairs = scheduler.filter_tasks(owner=owner, day=tomorrow, pet_name="Mochi", completed=False)
    if tomorrow_pairs:
        print("Tomorrow's newly generated tasks for Mochi:")
        for t in scheduler.sort_by_time([t for (_p, t) in tomorrow_pairs]):
            print(f"  - {t.due_date.isoformat()} {t.at.strftime('%H:%M')} {t.description} ({t.frequency})")
    else:
        print("No recurring tasks were generated for tomorrow.")


def run_agent_demo(owner: Owner) -> None:
    """Run the AI agent demo with observable intermediate steps."""
    print("\n" + "=" * 60)
    print("PART 2: AI Agent Workflow")
    print("=" * 60)

    try:
        from pawpal_agent import PawPalAgent
    except ImportError as e:
        print(f"\nCould not import agent module: {e}")
        print("Make sure 'anthropic' is installed: pip install anthropic")
        return

    import os
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("\nSet ANTHROPIC_API_KEY to run the AI agent demo.")
        print("  export ANTHROPIC_API_KEY='your-key-here'")
        return

    agent = PawPalAgent(owner)

    print("\n[Agent] Starting multi-step planning...\n")
    result = agent.run("Build a complete care plan for today. Pay attention to conflicts and suggest how to resolve them.")

    print(f"[Agent] Completed in {result['step_count']} tool-call steps.\n")

    print("--- Agent Tool Steps ---")
    for i, step in enumerate(result["steps"], 1):
        print(f"\n  Step {i}: {step['tool']}({step['input']})")
        if "warnings" in step["output"]:
            print(f"    Warnings: {step['output']['warnings']}")
        if "conflicts" in step["output"]:
            print(f"    Conflicts: {step['output']['conflicts']}")
        if "schedule" in step["output"]:
            print(f"    Tasks found: {len(step['output']['schedule'])}")
        if "pets" in step["output"]:
            print(f"    Pets: {[p['name'] for p in step['output']['pets']]}")
        if "tasks" in step["output"]:
            print(f"    Tasks: {len(step['output']['tasks'])}")

    print("\n--- AI Care Plan ---")
    print(result["plan"])

    print("\n--- Self-Check Guardrail ---")
    validation = agent.validate_plan(result)
    print(f"  Valid: {validation.get('valid')}")
    print(f"  Confidence: {validation.get('confidence')}")
    if validation.get("issues"):
        print(f"  Issues: {validation['issues']}")
    else:
        print("  Issues: None")


def main() -> None:
    owner = build_demo_owner()
    run_scheduler_demo(owner)

    owner2 = build_demo_owner()
    run_agent_demo(owner2)


if __name__ == "__main__":
    main()
