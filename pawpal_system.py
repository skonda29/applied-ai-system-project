"""PawPal+ backend logic layer with an integrated agentic workflow."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Iterable, List, Optional

logger = logging.getLogger("pawpal")

PRIORITY_SCORES = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


@dataclass
class Task:
    """Represents a single care activity that can be scheduled."""

    description: str
    at: time
    due_date: date = field(default_factory=date.today)
    frequency: str = "once"
    completed: bool = False
    duration_minutes: int = 30
    priority: str = "medium"
    notes: str = ""

    def __post_init__(self) -> None:
        self.frequency = self.frequency.strip().lower()
        self.priority = self.priority.strip().lower()
        if self.duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

    def end_time(self) -> time:
        """Return the estimated end time based on duration."""

        end_dt = datetime.combine(self.due_date, self.at) + timedelta(minutes=self.duration_minutes)
        return end_dt.time()

    def priority_score(self) -> int:
        """Return a numeric priority score."""

        return PRIORITY_SCORES.get(self.priority, 0)

    def mark_complete(self) -> Optional["Task"]:
        """Mark this task as completed and return the next recurring instance."""

        self.completed = True
        return self._next_recurring_instance()

    def _next_recurring_instance(self) -> Optional["Task"]:
        """Create the next task instance for recurring tasks."""

        if self.frequency == "daily":
            next_date = self.due_date + timedelta(days=1)
        elif self.frequency == "weekly":
            next_date = self.due_date + timedelta(days=7)
        else:
            return None

        return Task(
            description=self.description,
            at=self.at,
            due_date=next_date,
            frequency=self.frequency,
            completed=False,
            duration_minutes=self.duration_minutes,
            priority=self.priority,
            notes=self.notes,
        )


@dataclass
class Pet:
    """Stores pet details and a list of tasks."""

    pet_id: str
    name: str
    species: str
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        self.tasks.append(task)
        logger.info("Added task '%s' for pet '%s' on %s", task.description, self.name, task.due_date)

    def tasks_for_day(self, day: date) -> List[Task]:
        return [t for t in self.tasks if t.due_date == day]

    def mark_task_complete(
        self,
        *,
        description: str,
        at: time,
        day: date,
    ) -> bool:
        for task in self.tasks:
            if task.description == description and task.at == at and task.due_date == day:
                next_task = task.mark_complete()
                logger.info("Completed task '%s' for pet '%s' on %s", description, self.name, day)
                if next_task is not None:
                    self.add_task(next_task)
                return True
        logger.warning("Could not complete task '%s' for pet '%s' on %s", description, self.name, day)
        return False

    def remove_task(self, task: Task) -> None:
        self.tasks.remove(task)
        logger.info("Removed task '%s' from pet '%s'", task.description, self.name)


@dataclass
class Owner:
    """Manages multiple pets and provides access to their tasks."""

    owner_name: str
    pets: List[Pet] = field(default_factory=list)

    def add_pet(self, pet: Pet) -> None:
        self.pets.append(pet)
        logger.info("Added pet '%s' (%s) to owner '%s'", pet.name, pet.species, self.owner_name)

    def all_tasks(self) -> List[tuple[Pet, Task]]:
        pairs: List[tuple[Pet, Task]] = []
        for pet in self.pets:
            for task in pet.tasks:
                pairs.append((pet, task))
        return pairs

    def find_pet_by_name(self, name: str) -> Optional[Pet]:
        needle = name.strip().lower()
        for pet in self.pets:
            if pet.name.strip().lower() == needle:
                return pet
        return None


@dataclass
class PlannerResult:
    """Stores the output of the plan-act-check workflow."""

    schedule: List[dict]
    warnings: List[str]
    deferred_tasks: List[dict]
    confidence_score: float
    trace: List[str]
    review_notes: List[str]


class Scheduler:
    """The planning engine that retrieves, schedules, validates, and explains tasks."""

    def sort_by_time(self, tasks: Iterable[Task]) -> List[Task]:
        return sorted(tasks, key=lambda t: (t.at, t.description))

    def filter_tasks(
        self,
        *,
        owner: Owner,
        day: Optional[date] = None,
        pet_name: Optional[str] = None,
        completed: Optional[bool] = None,
    ) -> List[tuple[Pet, Task]]:
        pairs = owner.all_tasks()

        if day is not None:
            pairs = [(p, t) for (p, t) in pairs if t.due_date == day]

        if pet_name is not None:
            needle = pet_name.strip().lower()
            pairs = [(p, t) for (p, t) in pairs if p.name.strip().lower() == needle]

        if completed is not None:
            pairs = [(p, t) for (p, t) in pairs if t.completed == completed]

        return pairs

    def _task_to_item(self, pet: Pet, task: Task) -> dict:
        return {
            "time": task.at,
            "end_time": task.end_time(),
            "date": task.due_date,
            "pet_name": pet.name,
            "pet_id": pet.pet_id,
            "species": pet.species,
            "description": task.description,
            "frequency": task.frequency,
            "completed": task.completed,
            "duration_minutes": task.duration_minutes,
            "priority": task.priority,
            "priority_score": task.priority_score(),
            "notes": task.notes,
            "rationale": "",
        }

    def build_schedule(
        self,
        *,
        owner: Owner,
        day: Optional[date] = None,
    ) -> tuple[List[dict], List[str]]:
        if day is None:
            day = date.today()

        items = [
            self._task_to_item(pet, task)
            for pet, task in self.filter_tasks(owner=owner, day=day, completed=False)
        ]
        items.sort(key=lambda x: (x["time"], x["pet_name"], x["description"]))
        warnings = self.detect_conflicts(items)
        return items, warnings

    def todays_schedule(self, *, owner: Owner, day: Optional[date] = None) -> List[dict]:
        schedule, _warnings = self.build_schedule(owner=owner, day=day)
        return schedule

    def detect_conflicts(self, schedule: Iterable[dict]) -> List[str]:
        warnings: List[str] = []
        items = sorted(schedule, key=lambda x: (x["date"], x["time"], x["pet_name"], x["description"]))

        by_start_time: dict[tuple[date, time], List[dict]] = {}
        for item in items:
            key = (item["date"], item["time"])
            by_start_time.setdefault(key, []).append(item)

        for (_d, start), same_start_items in by_start_time.items():
            if len(same_start_items) > 1:
                pets = sorted({it["pet_name"] for it in same_start_items})
                warnings.append(
                    f"Conflict at {start.strftime('%H:%M')}: concurrent tasks for {', '.join(pets)}."
                )

        for earlier, later in zip(items, items[1:]):
            if earlier["date"] != later["date"]:
                continue
            earlier_end = datetime.combine(earlier["date"], earlier["end_time"])
            later_start = datetime.combine(later["date"], later["time"])
            if earlier_end > later_start:
                warnings.append(
                    f"Overlap detected: {earlier['pet_name']} {earlier['description']} runs until "
                    f"{earlier['end_time'].strftime('%H:%M')}, overlapping with "
                    f"{later['pet_name']} {later['description']} at {later['time'].strftime('%H:%M')}."
                )
        return warnings

    def _priority_sort_key(self, item: dict) -> tuple[int, time, str]:
        return (-item["priority_score"], item["time"], item["description"])

    def _create_rationale(self, item: dict) -> str:
        rationale = [
            f"{item['priority'].title()} priority",
            f"{item['duration_minutes']} min",
            f"scheduled at {item['time'].strftime('%H:%M')}",
        ]
        if item["frequency"] != "once":
            rationale.append(f"{item['frequency']} recurring care")
        return "; ".join(rationale)

    def generate_agentic_plan(
        self,
        *,
        owner: Owner,
        day: Optional[date] = None,
        pet_name: Optional[str] = None,
        available_minutes: Optional[int] = None,
    ) -> PlannerResult:
        if day is None:
            day = date.today()

        trace = [f"Plan: collect incomplete tasks for {day.isoformat()}."]
        pairs = self.filter_tasks(owner=owner, day=day, pet_name=pet_name, completed=False)
        candidates = [self._task_to_item(pet, task) for pet, task in pairs]
        logger.info("Planning run started for %s with %s candidate tasks", owner.owner_name, len(candidates))

        if not candidates:
            trace.append("Act: no eligible tasks found.")
            trace.append("Check: no conflicts because the plan is empty.")
            return PlannerResult(
                schedule=[],
                warnings=[],
                deferred_tasks=[],
                confidence_score=1.0,
                trace=trace,
                review_notes=["Human review: no tasks were available to verify."],
            )

        candidates.sort(key=self._priority_sort_key)
        trace.append("Act: rank tasks by priority, then by requested time.")

        schedule: List[dict] = []
        deferred: List[dict] = []
        used_minutes = 0

        for item in candidates:
            item["rationale"] = self._create_rationale(item)
            would_exceed_budget = (
                available_minutes is not None
                and schedule
                and used_minutes + item["duration_minutes"] > available_minutes
            )
            if would_exceed_budget:
                item["defer_reason"] = (
                    f"Deferred because adding {item['description']} would exceed the "
                    f"{available_minutes}-minute daily budget."
                )
                deferred.append(item)
                continue

            schedule.append(item)
            used_minutes += item["duration_minutes"]

        schedule.sort(key=lambda x: (x["time"], x["pet_name"], x["description"]))
        trace.append(f"Act: scheduled {len(schedule)} task(s) using {used_minutes} minute(s).")
        if deferred:
            trace.append(f"Act: deferred {len(deferred)} lower-ranked task(s) to stay within guardrails.")

        warnings = self.detect_conflicts(schedule)
        if deferred:
            warnings.extend(item["defer_reason"] for item in deferred)

        review_notes = [
            "Human review: check deferred tasks and confirm they can wait safely.",
        ]
        if warnings:
            review_notes.append("Human review: resolve any overlap/conflict warnings before relying on the plan.")
        else:
            review_notes.append("Human review: spot-check timing and pet assignments for correctness.")

        confidence_score = self._score_plan(schedule=schedule, warnings=warnings, deferred=deferred)
        trace.append(
            f"Check: validation finished with {len(warnings)} warning(s); confidence {confidence_score:.2f}."
        )

        logger.info(
            "Planning run finished for %s with %s scheduled and %s deferred tasks",
            owner.owner_name,
            len(schedule),
            len(deferred),
        )

        return PlannerResult(
            schedule=schedule,
            warnings=warnings,
            deferred_tasks=deferred,
            confidence_score=confidence_score,
            trace=trace,
            review_notes=review_notes,
        )

    def _score_plan(self, *, schedule: List[dict], warnings: List[str], deferred: List[dict]) -> float:
        penalty = 0.0
        penalty += 0.18 * sum(1 for warning in warnings if "Overlap" in warning or "Conflict" in warning)
        penalty += 0.05 * len(deferred)
        penalty += 0.1 * sum(1 for item in schedule if item["priority_score"] == 0)
        return max(0.0, min(1.0, round(1.0 - penalty, 2)))

    def format_schedule(self, schedule: Iterable[dict]) -> str:
        lines: List[str] = []
        for item in schedule:
            lines.append(
                f"{item['time'].strftime('%H:%M')}-{item['end_time'].strftime('%H:%M')}  "
                f"{item['pet_name']}: {item['description']} "
                f"[{item['priority']}, {item['duration_minutes']} min]"
            )
        return "\n".join(lines) if lines else "(no tasks scheduled)"
