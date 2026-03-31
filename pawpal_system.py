"""
PawPal+ backend logic layer (skeleton only).

This module defines the core objects you will use to implement the scheduling
logic later and connect to the Streamlit UI in `app.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional


@dataclass
class Task:
    """
    A single care task (e.g., walk, feeding, meds) that should be scheduled.
    """

    title: str
    duration_minutes: int
    priority: str  # expected: "low" | "medium" | "high"

    # Optional metadata to support richer scheduling later.
    task_type: Optional[str] = None
    notes: Optional[str] = None

    def priority_score(self) -> int:
        """Convert priority into a numeric score for ordering.

        Skeleton/stub: implement mapping + any owner preference adjustments.
        """

        raise NotImplementedError


@dataclass
class Pet:
    """
    Represents one pet. Owns the tasks that must be scheduled.
    """

    pet_id: str
    name: str
    species: str

    preferences: Dict[str, Any] = field(default_factory=dict)
    tasks: List[Task] = field(default_factory=list)

    def add_task(self, task: Task) -> None:
        """Add a new task to this pet."""

        raise NotImplementedError

    def update_task(self, task_title: str, updates: Dict[str, Any]) -> None:
        """Update an existing task by title (or other identifier)."""

        raise NotImplementedError

    def remove_task(self, task_title: str) -> None:
        """Remove an existing task."""

        raise NotImplementedError


@dataclass
class Owner:
    """
    Represents the user/owner. Owns pets and may store preferences affecting
    scheduling.
    """

    owner_name: str
    pets: List[Pet] = field(default_factory=list)

    preferences: Dict[str, Any] = field(default_factory=dict)
    daily_time_budget_minutes: int = 240

    def add_pet(self, pet: Pet) -> None:
        """Add a pet to this owner."""

        raise NotImplementedError

    def update_preferences(self, updates: Dict[str, Any]) -> None:
        """Update owner-level preferences that influence scheduling."""

        raise NotImplementedError


class Scheduler:
    """
    Scheduling engine: selects and orders tasks under constraints, and returns
    a plan that can be displayed along with an explanation.
    """

    def generate_daily_plan(
        self,
        *,
        owner: Owner,
        day: date,
        available_minutes: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Generate a daily plan across all of the owner's pets.

        Returns a list of items (dicts) including scheduled start time and
        task metadata; exact schema is up to your implementation.
        """

        raise NotImplementedError

    def explain_plan(
        self,
        *,
        owner: Owner,
        plan: List[Dict[str, Any]],
        day: date,
    ) -> str:
        """Produce a human-readable explanation for why the plan was chosen."""

        raise NotImplementedError

