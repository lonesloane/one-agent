# Phase 0 — Model Exploration: Specification

> Validate which model provides minimum reasoning quality for tool selection
> in the ONE MP domain, **before** writing any application code.
>
> **Duration**: 1-2 days, parallel to domain discovery.
>
> **Prerequisite reading**: [`brainstorming/ONE-Agent-concept.md`](brainstorming/ONE-Agent-concept.md) (PoC strategy, tool sketches, evaluation criteria)

---

## 1. What We Are Evaluating (and What We Are Not)

**In scope**: the model's ability to reason about tool selection given a system
prompt and a set of tool schemas. Concretely:

- Does the model pick the right tool(s) for a given user intent?
- Does it populate arguments correctly from the conversation context?
- Does it sequence multi-step plans in the right order (lookup before create)?
- Does it ask for missing information rather than hallucinating values?

**Not in scope**: real database access, production backend integration, frontend
UI, session persistence. None of these exist yet, and none are needed.

### Why This Works Without a Running Application

The model's tool-selection decision is based entirely on:
1. The **system prompt** (domain context + behavioral rules)
2. The **tool schemas** (function name, parameter types, descriptions)
3. The **user message** (the intent to interpret)

The tools don't need real implementations — **stub tools** that return canned
synthetic results are sufficient. The Agent Framework runs its full agentic loop
(LLM inference -> tool calls -> execute stub -> feed result back -> LLM reasons
about next step), and we inspect the complete trace of tool calls the model made.

This approach has two advantages over raw API calls:
1. **No agentic loop reimplementation**: the multi-step scenarios (B1, B2) require
   feeding tool results back to the model and letting it decide the next step.
   The Agent Framework does this natively — writing it manually is reimplementing
   the same loop.
2. **Tests the real integration path**: if the framework formats tool schemas
   differently, adds system prompt preamble, or handles tool results in a way that
   affects model behavior, we catch it now — not in Phase 1.

---

## 2. Candidate Models

All models are accessed via Azure AI Foundry using `FoundryChatClient`, within
the scope of a Visual Studio Enterprise subscription (limited Azure credits).

| Model | Tier | Notes |
|---|---|---|
| `gpt-5.4-nano` | Cheapest | Newest generation, nano class — baseline |
| `gpt-4.1-nano` | Cheapest | Previous generation nano — baseline |
| `gpt-5.4-mini` | Low | Newest generation mini — primary candidate |
| `gpt-4.1-mini` | Low | Previous generation mini, good tool use — primary candidate |
| `o4-mini` | Low | Reasoning model (chain-of-thought) — potentially strong on multi-step |
| `grok-3-mini` | Low | xAI model — included for diversity, less known for tool use |

**Decision rule**: select the cheapest model that passes all four evaluation
criteria (see §4) on >= 85% of test prompts. The two nano models set the
baseline; if neither mini-tier model qualifies, `o4-mini` (reasoning model) is
the ceiling before we'd need to flag a budget constraint.

---

## 3. Evaluation Inputs

### 3.1 System Prompt

The system prompt encodes the ONE MP domain, the user's role, and behavioral
rules. This is a static string used identically across all models and all test
prompts.

```text
You are ONE Agent, an assistant for the ONE MP platform at the OECD.
You help delegation editors and delegates manage delegate records, committee
participations, document access rights, and meeting preparation.

Behavioral rules:
- Always confirm write operations before executing them.
- When information is missing, ask the user — do not guess or invent values.
- When creating a delegate, always determine the correct Document Access Rights
  based on the delegation's membership type (member or partner) and the
  delegate's committee participations.
- Member delegates get General + Restricted access for their committees.
- Partner delegates get General access only (unless a Framework Agreement
  covers the committee, in which case they get Restricted).
- Confidential access and retroactive access require OECD secretariat approval.
- Approval routing: General -> auto-approved; Restricted -> delegation head;
  Confidential or retroactive -> secretariat.
- Before creating a new delegate, always look up whether they already exist.
- Before creating Document Access Rights, always retrieve the delegation's
  information to determine membership type and check for Framework Agreements.
```

### 3.2 Tool Stubs

Six tools, matching the concept doc. Defined as `@tool`-decorated Python
functions with full type annotations and descriptions — the same way they'll
be defined in the real agent (Phases 3-4). The implementations return canned
synthetic results that are sufficient for the model to reason through multi-step
sequences.

Synthetic results are parameterized per test scenario (see §5) so the same tool
can return different data depending on the test case being evaluated.

```python
# eval/tools.py
from typing import Annotated
from pydantic import Field
from agent_framework import tool

# --- Scenario-specific synthetic results ---
# Injected at test setup time; tools read from this dict.
SCENARIO_DATA: dict = {}


# --- Read tools ---

@tool(approval_mode="never_require")
def get_delegation_info(
    delegation_id: Annotated[str, Field(description="Delegation ID or country/organization name")],
) -> str:
    """Look up delegation information by ID or country name."""
    return SCENARIO_DATA.get("get_delegation_info", '{"name": "Unknown", "type": "unknown", "delegates": 0}')


@tool(approval_mode="never_require")
def lookup_delegate(
    name: Annotated[str, Field(description="Delegate name to search for")],
    delegation_id: Annotated[str, Field(description="Delegation to search within")] = "",
) -> str:
    """Search for a delegate by name, optionally within a specific delegation."""
    return SCENARIO_DATA.get("lookup_delegate", "No delegate found matching the search criteria.")


@tool(approval_mode="never_require")
def get_upcoming_meetings(
    delegate_id: Annotated[str, Field(description="Delegate ID to look up meetings for")],
) -> str:
    """Retrieve upcoming meetings for a specific delegate."""
    return SCENARIO_DATA.get("get_upcoming_meetings", '{"meetings": []}')


@tool(approval_mode="never_require")
def get_agenda_documents(
    meeting_id: Annotated[str, Field(description="Meeting ID to retrieve agenda documents for")],
    since: Annotated[str, Field(description="ISO date - only return docs added/modified after this date")] = "",
) -> str:
    """Retrieve agenda documents for a meeting, optionally filtered by date."""
    return SCENARIO_DATA.get("get_agenda_documents", '{"documents": []}')


# --- Write tools ---

@tool(approval_mode="never_require")  # eval only — in production, use "always_require"
def create_delegate(
    full_name: Annotated[str, Field(description="Full name of the delegate")],
    delegation_id: Annotated[str, Field(description="Delegation this delegate belongs to")],
    function: Annotated[str, Field(description="Professional function")],
    email: Annotated[str, Field(description="Professional email address")],
    committee_ids: Annotated[list[str], Field(description="Committees the delegate will participate in")],
) -> str:
    """Create a new delegate record in the system."""
    return SCENARIO_DATA.get("create_delegate", f"Delegate '{full_name}' created (ID: DEL-2026-0891)")


@tool(approval_mode="never_require")  # eval only — in production, use "always_require"
def create_document_access_rights(
    delegate_id: Annotated[str, Field(description="Delegate to grant access to")],
    committee_id: Annotated[str, Field(description="Committee scoping the document access")],
    classification_level: Annotated[str, Field(description="Max classification: General, Restricted, or Confidential")],
    retroactive: Annotated[bool, Field(description="Include documents published before accreditation date")] = False,
) -> str:
    """Grant document access rights to a delegate for a specific committee."""
    return SCENARIO_DATA.get("create_document_access_rights", f"Access rights granted: delegate={delegate_id}, committee={committee_id}, level={classification_level}")


ALL_TOOLS: list = [
    get_delegation_info, lookup_delegate, get_upcoming_meetings,
    get_agenda_documents, create_delegate, create_document_access_rights,
]
```

**Note on `approval_mode`**: all eval tools use `approval_mode="never_require"` to suppress
human-in-the-loop prompts during automated evaluation. In the real agent (Phases 3-4),
write tools use `@tool(approval_mode="always_require")` for human confirmation.

### 3.3 Test Prompt Catalog

15 prompts organized by category. Each prompt specifies the user message, any
prior conversation context (simulated tool results for multi-turn tests), and
the expected model behavior.

#### Category A — Single-tool reads (straightforward intent)

**A1: Simple delegation lookup**
- User: `"What type of delegation does Brazil have?"`
- Expected: call `get_delegation_info` with `delegation_id` containing "Brazil" (or "BRA")
- Criteria tested: correct tool, valid args

**A2: Delegate search**
- User: `"Is there a delegate named Marie Laurent in our delegation?"`
- Context: user is from France delegation (established in system prompt or prior turn)
- Expected: call `lookup_delegate` with `name="Marie Laurent"`, `delegation_id` referencing France
- Criteria tested: correct tool, extracts name, infers delegation from context

**A3: Meeting schedule**
- User: `"What meetings do I have coming up?"`
- Context: user is delegate DEL-2026-0042
- Expected: call `get_upcoming_meetings` with `delegate_id="DEL-2026-0042"`
- Criteria tested: correct tool, uses context identity

**A4: Agenda documents**
- User: `"Show me the agenda documents for the next Education Policy Committee meeting"`
- Context: meeting ID MTG-EDU-2026-04 is known from prior turn
- Expected: call `get_agenda_documents` with `meeting_id="MTG-EDU-2026-04"`
- Criteria tested: correct tool, uses prior context

**A5: New documents since last visit**
- User: `"Any new documents since my last login?"`
- Context: meeting ID MTG-EDU-2026-04, last login 2026-03-15
- Expected: call `get_agenda_documents` with `meeting_id` and `since="2026-03-15"`
- Criteria tested: correct tool, populates optional `since` parameter

#### Category B — Multi-step reasoning (correct sequencing)

**B1: Delegate creation — full info provided**
- User: `"Add Marie Laurent to our delegation. She's an education policy advisor, email marie.laurent@diplomatie.gouv.fr, assign her to the Education Policy Committee."`
- Context: user is editor for France delegation (FRA)
- Expected sequence:
  1. `lookup_delegate(name="Marie Laurent", delegation_id="FRA")` — check existence first
  2. `get_delegation_info(delegation_id="FRA")` — determine membership type for DAR
  3. `create_delegate(...)` — with all provided fields
  4. `create_document_access_rights(...)` — with correct level based on membership type
- Criteria tested: multi-step sequencing, lookup-before-create, business rule awareness

**B2: Meeting brief — proactive flow**
- User: `"Hi, I just logged in."`
- Context: user is delegate DEL-2026-0042, last login 2026-03-15
- Expected sequence:
  1. `get_upcoming_meetings(delegate_id="DEL-2026-0042")`
  2. For each meeting: `get_agenda_documents(meeting_id=..., since="2026-03-15")`
- Criteria tested: proactive behavior, multi-step, uses optional param

#### Category C — Missing information handling (asks vs invents)

**C1: Delegate creation — missing email**
- User: `"Add Jean Dupont as a trade analyst for France, he'll be on the Trade Committee."`
- Expected: model should NOT call `create_delegate` yet. Should ask for the missing email address.
- Criteria tested: asks for missing required field, does not invent

**C2: Delegate creation — missing committee**
- User: `"I need to add a new delegate, Sophie Martin, she's an economist."`
- Expected: model should ask for committee assignment(s) and email. Should NOT guess committees from job title alone.
- Criteria tested: asks for multiple missing fields, does not over-infer

**C3: Ambiguous delegation**
- User: `"Add a delegate to our delegation — Pierre Blanc, he works on development aid."`
- Context: no delegation established in conversation
- Expected: model should ask which delegation the user belongs to before proceeding.
- Criteria tested: asks for missing context, does not assume

#### Category D — Business rule reasoning

**D1: Member delegate — correct access level**
- User: `"Create DAR for delegate DEL-2026-0891, Education Policy Committee. Our delegation is a member country."`
- Expected: call `create_document_access_rights` with `classification_level="Restricted"` (member -> Restricted)
- Criteria tested: applies business rule correctly

**D2: Partner delegate — correct access level**
- User: `"Create DAR for delegate DEL-2026-0500, Trade Committee. We're a partner organization, no framework agreement for this committee."`
- Expected: call `create_document_access_rights` with `classification_level="General"` (partner without FA -> General)
- Criteria tested: applies business rule correctly

**D3: Partner with Framework Agreement**
- User: `"Create DAR for delegate DEL-2026-0500, Trade Committee. We're a partner but we have a Framework Agreement covering Trade."`
- Expected: call `create_document_access_rights` with `classification_level="Restricted"` (partner + FA -> Restricted)
- Criteria tested: applies conditional business rule

**D4: Confidential access — flags approval requirement**
- User: `"I need Confidential access for delegate DEL-2026-0891 on the Education Policy Committee."`
- Expected: model should acknowledge that Confidential requires secretariat approval, then call `create_document_access_rights` with `classification_level="Confidential"`. May ask for explicit confirmation given the elevated approval requirement.
- Criteria tested: business rule awareness, communicates implications

**D5: Retroactive access — flags approval requirement**
- User: `"Grant delegate DEL-2026-0891 access to Education Policy Committee documents, including documents from before their accreditation."`
- Expected: call `create_document_access_rights` with `retroactive=true` and appropriate classification level. Should communicate that retroactive access requires secretariat approval.
- Criteria tested: populates optional boolean, business rule awareness

---

## 4. Evaluation Criteria & Scoring

Each test prompt is scored on four criteria. Each criterion is binary (pass/fail)
per prompt.

| # | Criterion | What passes | What fails |
|---|---|---|---|
| C1 | **Correct tool** | Model selects the right tool(s) for the intent. No hallucinated tool names. | Wrong tool, made-up tool name, or no tool call when one is expected |
| C2 | **Schema-valid arguments** | All required parameters present with correct types. Values extracted from context, not invented. | Missing required params, wrong types, hallucinated values (e.g., invented email) |
| C3 | **Multi-step sequencing** | When multiple tools are needed, they are called in a logically correct order (lookup before create, get_delegation_info before DAR creation) | Wrong order, skipped prerequisite steps, or collapsed steps that should be separate |
| C4 | **Asks vs invents** | When required information is missing from the conversation, model asks the user rather than filling in plausible-sounding values | Invents an email, guesses a committee from a job title, assumes a delegation |

### Scoring per prompt

Each prompt has 1-4 applicable criteria (not all criteria apply to every prompt — e.g., single-tool prompts don't test C3). The prompt-level score is:

```
prompt_score = passing_criteria / applicable_criteria
```

### Scoring per model

```
model_score = sum(prompt_scores) / number_of_prompts
```

**Pass threshold**: model_score >= 0.85 (85%)

### Per-criterion breakdown

Also compute per-criterion pass rates to identify specific weaknesses:

```
criterion_pass_rate = prompts_passing_criterion / prompts_where_criterion_applies
```

A model that scores 90% overall but only 60% on C4 (asks vs invents) is not
suitable — it will hallucinate values in production. **Each criterion must
independently pass >= 75%** in addition to the aggregate 85%.

### Criteria applicability per prompt

| Prompt | C1 | C2 | C3 | C4 |
|--------|----|----|----|----|
| A1     | x  | x  |    |    |
| A2     | x  | x  |    |    |
| A3     | x  | x  |    |    |
| A4     | x  | x  |    |    |
| A5     | x  | x  |    |    |
| B1     | x  | x  | x  | x  |
| B2     | x  | x  | x  |    |
| C1     | x  |    |    | x  |
| C2     |    |    |    | x  |
| C3     |    |    |    | x  |
| D1     | x  | x  |    |    |
| D2     | x  | x  |    |    |
| D3     | x  | x  |    |    |
| D4     | x  | x  |    | x  |
| D5     | x  | x  |    |    |

---

## 5. Evaluation Harness

### Architecture

The harness uses the Microsoft Agent Framework to run each test scenario through
a real agentic loop — the same `Agent` + `@tool` + middleware stack that the
production agent will use. This avoids reimplementing the multi-turn tool-call
loop and ensures we're testing model behavior through the actual framework path.

A `RecorderMiddleware` (function middleware) intercepts every tool call and
captures the tool name, arguments, and result. After the agent finishes, the
recorded trace is scored against the expected behavior for that scenario.

```
eval/
  __init__.py                  # Package init
  tools.py                     # Stub tools with @tool decorators (§3.2)
  middleware.py                 # RecorderMiddleware — captures tool call trace
  evaluators.py                # Scoring functions per criterion (C1 done; C2-C4 Phase 0b)
  harness.py                   # Main evaluation script — runs Agent per model x scenario
  scenarios/
    scenarios.json             # Test catalog: prompts, scenario data, expected behavior (§3.3)
  results/                     # Output directory (gitignored)
    results_YYYY-MM-DD.json    # Raw traces + scores
```

### RecorderMiddleware

```python
# eval/middleware.py
from collections.abc import Awaitable, Callable
from agent_framework import FunctionMiddleware, FunctionInvocationContext

class RecorderMiddleware(FunctionMiddleware):
    """Captures every tool call for post-hoc evaluation."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[dict] = []

    async def process(
        self,
        context: FunctionInvocationContext,
        call_next: Callable[[], Awaitable[None]],
    ) -> None:
        record = {
            "tool": context.function.name,
            "arguments": dict(context.arguments),
        }
        await call_next()           # call_next takes NO arguments
        record["result"] = context.result
        self.calls.append(record)

    def reset(self) -> None:
        self.calls = []
```

### Harness core loop

```python
# eval/harness.py (simplified)
import asyncio, json, os
from pathlib import Path
from azure.identity.aio import AzureCliCredential   # async version required
from agent_framework import Agent
from agent_framework.foundry import FoundryChatClient
from eval.tools import ALL_TOOLS, SCENARIO_DATA
from eval.middleware import RecorderMiddleware
from eval.evaluators import score_scenario

SYSTEM_PROMPT = "..."  # §3.1 — loaded from constant in harness.py

DEFAULT_MODEL = "gpt-4.1-mini"

SCENARIOS_PATH = Path(__file__).parent / "scenarios" / "scenarios.json"


async def evaluate_scenario(model: str, scenario: dict) -> dict:
    """Run one scenario through one model and return the scored trace."""
    endpoint = os.environ["FOUNDRY_PROJECT_ENDPOINT"]   # from .env

    SCENARIO_DATA.clear()
    SCENARIO_DATA.update(scenario.get("synthetic_results", {}))

    instructions = SYSTEM_PROMPT
    if scenario.get("system_context"):
        instructions += f"\n\n{scenario['system_context']}"

    recorder = RecorderMiddleware()

    async with (
        AzureCliCredential() as credential,
        Agent(
            client=FoundryChatClient(
                project_endpoint=endpoint,
                model=model,
                credential=credential,
            ),
            name="ONEAgent-Eval",
            instructions=instructions,
            tools=ALL_TOOLS,
            middleware=[recorder],
        ) as agent,
    ):
        result = await agent.run(scenario["user_message"])

    scores = score_scenario(
        scenario_id=scenario["id"],
        tool_calls=recorder.calls,
        agent_response=result.text,
        expected=scenario["expected"],
    )
    return {
        "model": model,
        "scenario_id": scenario["id"],
        "tool_calls": recorder.calls,
        "agent_response": result.text,
        "scores": {"criteria": scores.criteria, "details": scores.details},
    }


async def run_all(model: str = DEFAULT_MODEL) -> list[dict]:
    with open(SCENARIOS_PATH) as f:
        scenarios = json.load(f)
    return [await evaluate_scenario(model, s) for s in scenarios]


if __name__ == "__main__":
    asyncio.run(run_all())
```

### Scenario format (scenarios.json)

```json
{
  "id": "B1",
  "category": "multi_step",
  "description": "Delegate creation — full info provided",
  "system_context": "User is editor for France delegation (FRA).",
  "user_message": "Add Marie Laurent to our delegation. She's an education policy advisor, email marie.laurent@diplomatie.gouv.fr, assign her to the Education Policy Committee.",
  "synthetic_results": {
    "lookup_delegate": "No delegate found matching 'Marie Laurent'.",
    "get_delegation_info": "{\"name\": \"France\", \"type\": \"member\", \"delegates\": 42, \"framework_agreements\": []}",
    "create_delegate": "Delegate 'Marie Laurent' created (ID: DEL-2026-0891)",
    "create_document_access_rights": "DAR created: delegate=DEL-2026-0891, committee=EDU, level=Restricted"
  },
  "expected": {
    "tool_calls_ordered": [
      { "name": "lookup_delegate", "args_must_contain": { "name": "Marie Laurent" } },
      { "name": "get_delegation_info", "args_must_contain": {} },
      { "name": "create_delegate", "args_must_contain": { "full_name": "Marie Laurent", "email": "marie.laurent@diplomatie.gouv.fr" } },
      { "name": "create_document_access_rights", "args_must_contain": { "classification_level": "Restricted" } }
    ],
    "must_not_hallucinate": ["email", "committee_ids"],
    "should_ask_user": false,
    "applicable_criteria": ["C1", "C2", "C3", "C4"]
  }
}
```

### Running the harness

```bash
# Prerequisites
az login
cp .env.example .env   # then fill in FOUNDRY_PROJECT_ENDPOINT
source .venv/bin/activate

# Run all 3 Phase 0a scenarios on gpt-4.1-mini (default)
python -m eval.harness

# Phase 0b: run against a different model (extend run_all() model list)
python -c "import asyncio; from eval.harness import run_all; asyncio.run(run_all('gpt-4.1-nano'))"
```

---

## 6. Infrastructure Prerequisites

Before running the evaluation:

All models are accessed via Azure AI Foundry — no local GPU or Ollama setup needed.

| Prerequisite | Status | Notes |
|---|---|---|
| Azure AI Foundry access via VS Enterprise | TBD | Need `FOUNDRY_PROJECT_ENDPOINT` in `.env` (see `.env.example`) |
| Model deployments | TBD | Start with `gpt-4.1-mini`; remaining 5 models for Phase 0b |
| `az login` (AzureCliCredential) | TBD | Required before running `python -m eval.harness` |
| Python environment | ✓ Done | `python3 -m venv .venv && pip install -e ".[dev]"` — all deps installed |

**Note**: the harness uses the Microsoft Agent Framework with `FoundryChatClient`
— the same stack the real agent will use in later phases. This means Phase 0
validates model capability *through the framework*, not in isolation. If the
framework's tool schema formatting or system prompt handling affects model
behavior, we catch it here rather than discovering it in Phase 1.

---

## 7. Expected Outputs

At the end of Phase 0, we have:

1. **A results table**: per-model, per-prompt, per-criterion scores
2. **A model decision**: which model to use for Phases 1-4, with rationale
3. **Identified weaknesses**: any criteria where even the chosen model is borderline (these become test cases to monitor as the agent evolves)
4. **Reusable test infrastructure**: the harness, prompts, and evaluators become the regression suite for later phases — as tools and prompts evolve, re-run to catch model regressions

### Decision matrix (template)

| Model | C1 (tool) | C2 (args) | C3 (sequence) | C4 (asks) | Aggregate | Cost | Decision |
|---|---|---|---|---|---|---|---|
| gpt-5.4-nano | ?% | ?% | ?% | ?% | ?% | Cheapest | Baseline |
| gpt-4.1-nano | ?% | ?% | ?% | ?% | ?% | Cheapest | Baseline |
| gpt-5.4-mini | ?% | ?% | ?% | ?% | ?% | Low | Primary candidate |
| gpt-4.1-mini | ?% | ?% | ?% | ?% | ?% | Low | Primary candidate |
| o4-mini | ?% | ?% | ?% | ?% | ?% | Low | Reasoning model |
| grok-3-mini | ?% | ?% | ?% | ?% | ?% | Low | Alternative |

---

## 8. Relationship to Later Phases

Phase 0 uses the same framework and tool signatures as later phases, but with
stub implementations instead of real backends. This creates a natural upgrade
path:

- **Shared tool signatures**: the `@tool` stubs in `eval/tools.py` define the
  exact function signatures, type annotations, and descriptions that the real
  tools will use. When Phase 3 implements real tools, the model sees identical
  schemas — no behavioral surprises.
- **Outputs feed Phase 1**: the model choice determines the `FoundryChatClient`
  model config for all subsequent phases.
- **Test prompts evolve**: as tools are implemented in Phase 1+, the test catalog
  grows. The harness structure and middleware stay the same.
- **Regression safety net**: before any model upgrade or prompt change in later
  phases, re-run the Phase 0 harness to check for regressions. The stub tools
  make this fast and free (no database or backend needed).
- **Middleware reuse**: the `RecorderMiddleware` pattern carries forward as a
  testing/debugging tool in later phases.
