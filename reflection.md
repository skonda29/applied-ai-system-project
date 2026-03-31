# PawPal+ Project Reflection

## 1. System Design

**a. Initial design**

- Briefly describe your initial UML design.
- What classes did you include, and what responsibilities did you assign to each?
- The user can (1) enter basic owner + pet info, 
(2) add/edit pet care tasks with duration and priority, and 
(3) generate a daily schedule/plan that fits within time constraints and shows an explanation for the chosen order.
- `Owner` stores the owner profile, owner-level scheduling preferences, and the list of `Pet` objects that belong to the owner.
- `Pet` stores pet identity (name/species), pet-level preferences, and the list of `Task` items that need to be scheduled.
- `Task` represents one care activity (title, duration, priority) and provides priority scoring behavior (stubbed for now) that the scheduler can use.
- `Scheduler` is responsible for taking the owner + day + constraints and producing an ordered daily plan (plus a human-readable explanation).

**b. Design changes**

- Did your design change during implementation?
- Yes. I expanded the initial `Task` concept to include `due_date` and `frequency`, and I changed `mark_complete()` to return a new recurring instance (so the next occurrence is created automatically). This kept recurrence logic in the backend model rather than duplicating it in the UI.

---

## 2. Scheduling Logic and Tradeoffs

**a. Constraints and priorities**

- The scheduler currently uses `due_date` and `completed` status to decide which tasks are eligible for a given day, and it orders tasks by the `at` time. Preferences/priority are out of scope for this module iteration, so time + recurrence + status are the main “constraints” enforced.
- I focused on the constraints that directly support the required user experience: consistent daily planning (filter by day), sensible ordering (sort by time), and usefulness for real routines (daily/weekly recurrence + conflicts).

**b. Tradeoffs**

- Describe one tradeoff your scheduler makes.
- Why is that tradeoff reasonable for this scenario?
- One tradeoff is that conflict detection only checks for exact same start times (for example, two tasks both at 08:00) instead of full duration overlap analysis.
- This is reasonable for the current project scope because it keeps the algorithm simple and easy to explain, while still catching the most obvious scheduling issues for a busy pet owner.
---

## 3. AI Collaboration

**a. How you used AI**

- I used Copilot Chat to translate the UML into dataclass-based code stubs, brainstorm small scheduling algorithms (sorting/filtering/conflict detection), and iterate on tests by generating missing edge-case coverage once I saw what the current suite didn’t test.
- The most helpful Copilot features were chat-based code generation and inline iteration (so I could adjust code in small steps). The most helpful prompts were “keep it minimal” requests (so changes stayed understandable), plus targeted questions like how the Scheduler should retrieve tasks from `Owner` and how to structure recurrence rollover for daily/weekly tasks.

**b. Judgment and verification**

- I rejected/modified an AI suggestion that would have expanded conflict detection into full interval overlap analysis. I simplified it to exact start-time conflicts because it was easier to explain, test, and keep the scheduler readable.
- I used separate chat sessions for different phases (design → implementation → algorithms → testing → UI/documentation) to keep my context organized and to avoid mixing decisions across phases.
- I verified suggestions by running the CLI demo and then adding/adjusting `pytest` tests for the specific behavior (recurring rollover and conflict warnings), so changes were backed by green tests rather than assumptions.

---

## 4. Testing and Verification

**a. What you tested**

- I tested the scheduler’s key behaviors and edge cases: sorting correctness, recurrence logic (daily completion creates next-day task), conflict detection for duplicate times, and the empty-state behavior when a pet has no tasks.
- These tests are important because the scheduler is the “brain” of the app: the Streamlit UI is mostly wiring, but the scheduling logic can silently break unless its core rules are verified automatically.

**b. Confidence**

- I’m confident for the current scope: the main algorithms (sorting/filtering/conflicts/recurrence rollover for daily) are covered and the test suite is passing.
- With more time, I would add tests for weekly recurrence, tasks on multiple dates, and more advanced conflict detection (overlapping durations rather than exact matches).

---

## 5. Reflection

**a. What went well**

- I’m most satisfied with how reusable and consistent the backend logic became. The same `Scheduler` methods power both the CLI demo and the Streamlit UI, and recurrence behavior is handled by the models.

**b. What you would improve**

- I would improve conflict detection to handle overlapping time ranges (based on durations) and expand the UI so the user can mark completion directly from the displayed schedule table instead of using a single selection demo.

**c. Key takeaway**

- My key takeaway is that AI is most effective when you treat it as a collaborator for drafts and options, but you keep ownership of system coherence. As the “lead architect,” I had to choose the right amount of complexity, ensure the class model matched the final behavior, and use tests/documentation to lock in the design rather than just follow suggestions.
