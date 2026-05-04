import logging
import os
from datetime import date
from uuid import uuid4

import streamlit as st

from pawpal_system import Owner, Pet, PlannerResult, Scheduler, Task

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

st.set_page_config(page_title="PawPal+", page_icon="🐾", layout="centered")

st.title("🐾 PawPal+")
st.caption("An agentic pet care planner that proposes, checks, and explains a daily care plan.")

if "owner" not in st.session_state:
    st.session_state.owner = Owner(owner_name="Jordan")
if "last_plan" not in st.session_state:
    st.session_state.last_plan = None

owner: Owner = st.session_state.owner

with st.expander("How the workflow operates", expanded=True):
    st.markdown(
        """
1. **Plan:** collect incomplete tasks for the selected day.
2. **Act:** rank tasks by priority and requested time, then build a schedule within the time budget.
3. **Check:** detect overlaps/conflicts, estimate confidence, and flag items that need human review.
"""
    )

owner.owner_name = st.text_input("Owner name", value=owner.owner_name)

st.markdown("### Pets")
colp1, colp2 = st.columns([2, 1])
with colp1:
    pet_name = st.text_input("Pet name", value="Mochi")
with colp2:
    species = st.selectbox("Species", ["dog", "cat", "other"])

if st.button("Add pet"):
    owner.add_pet(Pet(pet_id=str(uuid4()), name=pet_name, species=species))

if owner.pets:
    pet_options = {f"{pet.name} ({pet.species})": pet.pet_id for pet in owner.pets}
    selected_pet_label = st.selectbox("Select pet", list(pet_options.keys()))
    selected_pet_id = pet_options[selected_pet_label]
    selected_pet = next(pet for pet in owner.pets if pet.pet_id == selected_pet_id)
else:
    selected_pet = None
    st.info("Add a pet to start building a plan.")

st.markdown("### Tasks")
col1, col2 = st.columns(2)
with col1:
    description = st.text_input("Task description", value="Morning walk")
with col2:
    due_day = st.date_input("Due date", value=date.today())

col3, col4, col5 = st.columns(3)
with col3:
    at_time = st.time_input("Start time", value=None)
with col4:
    duration_minutes = st.number_input("Duration (minutes)", min_value=5, max_value=240, value=30, step=5)
with col5:
    priority = st.selectbox("Priority", ["low", "medium", "high", "critical"], index=2)

col6, col7 = st.columns(2)
with col6:
    frequency = st.selectbox("Frequency", ["once", "daily", "weekly"], index=1)
with col7:
    notes = st.text_input("Notes", value="Bring treats")

if st.button("Add task", disabled=selected_pet is None):
    if at_time is None:
        st.error("Choose a time before adding the task.")
    else:
        selected_pet.add_task(
            Task(
                description=description,
                at=at_time,
                due_date=due_day,
                frequency=frequency,
                duration_minutes=int(duration_minutes),
                priority=priority,
                notes=notes,
            )
        )
        st.success(f"Added {description} for {selected_pet.name}.")

if selected_pet and selected_pet.tasks:
    st.write("Current tasks for selected pet")
    st.table(
        [
            {
                "Due": task.due_date.isoformat(),
                "Time": task.at.strftime("%H:%M"),
                "Duration": task.duration_minutes,
                "Priority": task.priority,
                "Task": task.description,
                "Frequency": task.frequency,
                "Completed": task.completed,
            }
            for task in sorted(selected_pet.tasks, key=lambda task: (task.due_date, task.at, task.description))
        ]
    )

st.divider()
st.subheader("Generate Agentic Plan")

plan_day = st.date_input("Plan date", value=date.today(), key="plan_day")
available_minutes = st.slider("Daily care time budget", min_value=15, max_value=240, value=90, step=15)

if owner.pets:
    pet_filter_name = st.selectbox(
        "Plan for one pet or all pets",
        ["(all)"] + [pet.name for pet in owner.pets],
    )
    if pet_filter_name == "(all)":
        pet_filter_name = None
else:
    pet_filter_name = None

if st.button("Generate plan"):
    scheduler = Scheduler()
    st.session_state.last_plan = scheduler.generate_agentic_plan(
        owner=owner,
        day=plan_day,
        pet_name=pet_filter_name,
        available_minutes=available_minutes,
    )

result: PlannerResult | None = st.session_state.last_plan
if result is not None:
    st.markdown("#### Planned Schedule")
    if result.schedule:
        st.table(
            [
                {
                    "Time": f"{item['time'].strftime('%H:%M')} - {item['end_time'].strftime('%H:%M')}",
                    "Pet": item["pet_name"],
                    "Task": item["description"],
                    "Priority": item["priority"],
                    "Duration": item["duration_minutes"],
                    "Why chosen": item["rationale"],
                }
                for item in result.schedule
            ]
        )
    else:
        st.info("No tasks matched the current filters.")

    st.metric("Confidence score", f"{result.confidence_score:.2f}")

    if result.warnings:
        st.warning("Validation warnings")
        for warning in result.warnings:
            st.write(f"- {warning}")
    else:
        st.success("No validation warnings were found.")

    if result.deferred_tasks:
        st.markdown("#### Deferred Tasks")
        st.table(
            [
                {
                    "Pet": item["pet_name"],
                    "Task": item["description"],
                    "Priority": item["priority"],
                    "Reason": item["defer_reason"],
                }
                for item in result.deferred_tasks
            ]
        )

    st.markdown("#### Execution Trace")
    for step in result.trace:
        st.write(f"- {step}")

    st.markdown("#### Human Review Checklist")
    for note in result.review_notes:
        st.write(f"- {note}")

st.divider()
st.subheader("Complete a Task")

if selected_pet is None:
    st.info("Add and select a pet to enable task completion.")
else:
    todays_incomplete = [task for task in selected_pet.tasks if task.due_date == date.today() and not task.completed]
    todays_incomplete.sort(key=lambda task: (task.at, task.description))

    if not todays_incomplete:
        st.info("No incomplete tasks due today for this pet.")
    else:
        task_labels = [
            f"{task.at.strftime('%H:%M')} - {task.description} ({task.frequency}, {task.priority})"
            for task in todays_incomplete
        ]
        selected_task_label = st.selectbox("Task to mark complete", task_labels)
        selected_task_index = task_labels.index(selected_task_label)
        task = todays_incomplete[selected_task_index]

        if st.button("Mark complete"):
            did_complete = selected_pet.mark_task_complete(description=task.description, at=task.at, day=date.today())
            if did_complete:
                st.success("Task marked complete. Recurring work was rolled forward when needed.")
            else:
                st.error("The selected task could not be updated.")

st.divider()
st.subheader("AI Agent Plan (Claude)")

has_api_key = bool(os.environ.get("ANTHROPIC_API_KEY"))

if not has_api_key:
    st.info(
        "Set the **ANTHROPIC_API_KEY** environment variable to enable the AI agent. "
        "Run: `ANTHROPIC_API_KEY=sk-... streamlit run app.py`"
    )
else:
    if "agent_result" not in st.session_state:
        st.session_state.agent_result = None

    agent_prompt = st.text_input(
        "Ask the AI agent",
        value="Please build today's care plan for all my pets.",
        key="agent_prompt",
    )

    if st.button("Run AI Agent", disabled=not owner.pets):
        from pawpal_agent import PawPalAgent

        with st.spinner("Claude is reasoning through your schedule..."):
            try:
                agent = PawPalAgent(owner)
                plan_result = agent.run(agent_prompt)
                validation = agent.validate_plan(plan_result)
                st.session_state.agent_result = {
                    "plan": plan_result,
                    "validation": validation,
                }
            except Exception as exc:
                st.error(f"Agent error: {exc}")
                st.session_state.agent_result = None

    agent_data = st.session_state.get("agent_result")
    if agent_data is not None:
        plan_result = agent_data["plan"]
        validation = agent_data["validation"]

        st.markdown("#### AI-Generated Care Plan")
        st.markdown(plan_result["plan"])

        st.markdown("#### Agent Intermediate Steps")
        for i, step in enumerate(plan_result["steps"], 1):
            with st.expander(f"Step {i}: {step['tool']}"):
                st.json({"input": step["input"], "output": step["output"]})

        st.metric("Tool calls made", plan_result["step_count"])

        st.markdown("#### Self-Check Validation")
        vcol1, vcol2 = st.columns(2)
        with vcol1:
            st.metric("Valid", str(validation.get("valid", "N/A")))
        with vcol2:
            st.metric("Confidence", validation.get("confidence", "N/A"))
        if validation.get("issues"):
            st.warning("Validation issues")
            for issue in validation["issues"]:
                st.write(f"- {issue}")
        else:
            st.success("No validation issues found.")
