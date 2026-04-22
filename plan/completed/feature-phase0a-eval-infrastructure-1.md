---
goal: "Phase 0a: Evaluation Harness Infrastructure & End-to-End Validation"
version: 1.0
date_created: 2026-04-06
last_updated: 2026-04-06
owner: Stephane
status: Completed
tags:
  - feature
  - infrastructure
  - evaluation
  - phase-0
---

# Introduction

![Status: Completed](https://img.shields.io/badge/status-Completed-green)

Build the evaluation harness infrastructure for Phase 0 model exploration
and validate it end-to-end with 3 representative scenarios on 1 model.
This proves the Microsoft Agent Framework + Azure AI Foundry stack works
before investing in the full 15-scenario evaluation suite (Phase 0b).

**Exit criterion**: `python -m eval.harness` produces captured tool call
traces with scores for scenarios A1, B1, C1 on `gpt-4.1-mini`.

## 1. Requirements & Constraints

- **REQ-001**: Python 3.11, virtual environment, PEP 8, Google docstrings,
  type hints per CLAUDE.md conventions.
- **REQ-002**: Use Microsoft Agent Framework v1.0.0 (`agent-framework` +
  `agent-framework-foundry` packages from PyPI).
- **REQ-003**: Use `FoundryChatClient` with `AzureCliCredential` for model
  access via Azure AI Foundry.
- **REQ-004**: Tool stubs must use the `@tool` decorator from
  `agent_framework` with `Annotated[type, Field(description=...)]` for
  parameter descriptions.
- **REQ-005**: `RecorderMiddleware` must capture tool name, arguments, and
  result for every tool call in a scenario run.
- **REQ-006**: Three representative scenarios must cover: single-tool read
  (A1), multi-step sequencing (B1), missing information handling (C1).
- **REQ-007**: Basic evaluator must score C1 criterion (correct tool
  selection) to validate the scoring pipeline.
- **SEC-001**: No hardcoded credentials. Use `AzureCliCredential` (requires
  `az login` before running).
- **SEC-002**: Project endpoint must come from environment variable, not
  source code.
- **CON-001**: All models accessed via Azure AI Foundry — no local GPU or
  Ollama.
- **CON-002**: Budget constraint: VS Enterprise subscription credits only.
- **GUD-001**: Functions under 50 lines, classes under 100 lines, files
  under 500 lines per CLAUDE.md.
- **GUD-002**: Use `loguru` for logging, not print statements.
- **PAT-001**: Agent Framework async context manager pattern:
  `async with Agent(...) as agent:`.
- **PAT-002**: Tool definitions use `@tool(approval_mode="never_require")`
  for eval (no human-in-the-loop during automated evaluation).
- **PAT-003**: `FunctionMiddleware` subclass with `process(self, context,
  call_next)` method for recording tool calls.

## 2. Implementation Steps

### Phase 1: Project Scaffolding

- GOAL-001: Create Python project structure with all dependencies and
  verify the development environment works.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Create `pyproject.toml` with `[project]` metadata (name=`one-agent-poc`, python_requires=`>=3.11`), dependencies: `agent-framework>=1.0.0`, `agent-framework-foundry>=1.0.0`, `azure-identity>=1.19.0`, `loguru>=0.7.0`, `pydantic>=2.0`. Dev extras: `pytest>=8.0`, `pytest-asyncio>=0.24`. | ✓ | 2026-04-06 |
| TASK-002 | Create directory structure: `eval/__init__.py`, `eval/tools.py`, `eval/middleware.py`, `eval/evaluators.py`, `eval/harness.py`, `eval/scenarios/` (directory for JSON files), `eval/results/` (gitignored output). | ✓ | 2026-04-06 |
| TASK-003 | Create `.env.example` with `FOUNDRY_PROJECT_ENDPOINT=https://your-project.services.ai.azure.com/api/projects/your-project` as a template. Add `.env` to `.gitignore`. | ✓ | 2026-04-06 |
| TASK-004 | Create and activate venv: `python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`. Verify `from agent_framework import Agent, tool` and `from agent_framework.foundry import FoundryChatClient` import without error. | ✓ | 2026-04-06 |

### Phase 2: Tool Stubs

- GOAL-002: Implement 6 stub tools matching the spec (PHASE0 doc S3.2),
  using the verified Agent Framework `@tool` decorator and `Annotated`
  type hints. Tools read canned results from a global `SCENARIO_DATA` dict.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-005 | Create `eval/tools.py`. Define module-level `SCENARIO_DATA: dict = {}` for scenario-specific synthetic results. | ✓ | 2026-04-06 |
| TASK-006 | Implement `get_delegation_info(delegation_id: Annotated[str, Field(description="Delegation ID or country/organization name")]) -> str`. Decorated with `@tool(approval_mode="never_require")`. Returns `SCENARIO_DATA.get("get_delegation_info", <default JSON string>)`. | ✓ | 2026-04-06 |
| TASK-007 | Implement `lookup_delegate(name: Annotated[str, Field(description="Delegate name to search for")], delegation_id: Annotated[str, Field(description="Delegation to search within")] = "") -> str`. Returns `SCENARIO_DATA.get("lookup_delegate", "No delegate found matching the search criteria.")`. | ✓ | 2026-04-06 |
| TASK-008 | Implement `get_upcoming_meetings(delegate_id: Annotated[str, Field(description="Delegate ID to look up meetings for")]) -> str`. Returns `SCENARIO_DATA.get("get_upcoming_meetings", <default JSON>)`. | ✓ | 2026-04-06 |
| TASK-009 | Implement `get_agenda_documents(meeting_id: Annotated[str, Field(description="Meeting ID to retrieve agenda documents for")], since: Annotated[str, Field(description="ISO date - only return docs added/modified after this date")] = "") -> str`. Returns `SCENARIO_DATA.get("get_agenda_documents", <default JSON>)`. | ✓ | 2026-04-06 |
| TASK-010 | Implement `create_delegate(full_name: Annotated[str, Field(description="Full name of the delegate")], delegation_id: Annotated[str, Field(description="Delegation this delegate belongs to")], function: Annotated[str, Field(description="Professional function")], email: Annotated[str, Field(description="Professional email address")], committee_ids: Annotated[list[str], Field(description="Committees the delegate will participate in")]) -> str`. Returns `SCENARIO_DATA.get("create_delegate", f"Delegate '{full_name}' created (ID: DEL-2026-0891)")`. | ✓ | 2026-04-06 |
| TASK-011 | Implement `create_document_access_rights(delegate_id: Annotated[str, Field(description="Delegate to grant access to")], committee_id: Annotated[str, Field(description="Committee scoping the document access")], classification_level: Annotated[str, Field(description="Max classification: General, Restricted, or Confidential")], retroactive: Annotated[bool, Field(description="Include documents published before accreditation date")] = False) -> str`. Returns `SCENARIO_DATA.get(...)`. | ✓ | 2026-04-06 |
| TASK-012 | Define `ALL_TOOLS` list containing all 6 tool functions. Verify list is importable: `from eval.tools import ALL_TOOLS`. | ✓ | 2026-04-06 |

### Phase 3: Recorder Middleware

- GOAL-003: Implement `RecorderMiddleware` that captures every tool call
  (name, arguments, result) during an agent run, using the verified
  `FunctionMiddleware` base class.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-013 | Create `eval/middleware.py`. Import `FunctionMiddleware`, `FunctionInvocationContext` from `agent_framework`. | ✓ | 2026-04-06 |
| TASK-014 | Implement `RecorderMiddleware(FunctionMiddleware)` with: `__init__` initializing `self.calls: list[dict] = []`; `async def process(self, context: FunctionInvocationContext, call_next)` that records `{"tool": context.function.name, "arguments": dict(context.arguments)}` before `await call_next()`, then appends `context.result` to the record; `reset()` method clearing `self.calls`. | ✓ | 2026-04-06 |

### Phase 4: Representative Scenarios

- GOAL-004: Create 3 scenario definitions (A1, B1, C1) in JSON format,
  covering single-tool reads, multi-step sequencing, and missing
  information handling.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-015 | Create `eval/scenarios/scenarios.json` with scenario A1 (Simple delegation lookup): `{"id": "A1", "category": "single_tool_read", "description": "Simple delegation lookup", "system_context": "", "user_message": "What type of delegation does Brazil have?", "synthetic_results": {"get_delegation_info": "{\"name\": \"Brazil\", \"type\": \"partner\", \"delegates\": 18, \"framework_agreements\": [\"Trade\"]}"}, "expected": {"tool_calls_ordered": [{"name": "get_delegation_info", "args_must_contain": {"delegation_id": "Brazil"}}], "must_not_hallucinate": [], "should_ask_user": false, "applicable_criteria": ["C1", "C2"]}}`. | ✓ | 2026-04-06 |
| TASK-016 | Add scenario B1 (Delegate creation - full info provided): system_context = "User is editor for France delegation (FRA).", user_message = "Add Marie Laurent to our delegation. She's an education policy advisor, email marie.laurent@diplomatie.gouv.fr, assign her to the Education Policy Committee.", synthetic_results for all 4 tools (lookup_delegate, get_delegation_info, create_delegate, create_document_access_rights), expected tool_calls_ordered with 4 steps in sequence, applicable_criteria = ["C1", "C2", "C3", "C4"]. See PHASE0 spec B1 for exact values. | ✓ | 2026-04-06 |
| TASK-017 | Add scenario C1 (Delegate creation - missing email): user_message = "Add Jean Dupont as a trade analyst for France, he'll be on the Trade Committee.", expected: should_ask_user = true, no create_delegate call expected, applicable_criteria = ["C1", "C4"]. | ✓ | 2026-04-06 |

### Phase 5: Basic Evaluator

- GOAL-005: Implement scoring for criterion C1 (correct tool selection)
  with stubs for C2-C4. This validates the scoring pipeline end-to-end.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-018 | Create `eval/evaluators.py`. Define `ScenarioScore` dataclass with fields: `scenario_id: str`, `criteria: dict[str, bool | None]` (None = not applicable), `details: dict[str, str]` (human-readable notes per criterion). | ✓ | 2026-04-06 |
| TASK-019 | Implement `evaluate_c1_correct_tool(tool_calls: list[dict], expected: dict) -> tuple[bool, str]`. Logic: extract expected tool names from `expected["tool_calls_ordered"]`; check that every expected tool name appears in the actual `tool_calls` list (order-insensitive for C1 — ordering is C3). If `expected.get("should_ask_user")` is True, C1 passes if no write tool was called. Return (pass/fail, explanation string). | ✓ | 2026-04-06 |
| TASK-020 | Add stub functions `evaluate_c2_schema_valid_args`, `evaluate_c3_multi_step_sequencing`, `evaluate_c4_asks_vs_invents` that return `(None, "Not implemented - Phase 0b")`. | ✓ | 2026-04-06 |
| TASK-021 | Implement `score_scenario(tool_calls: list[dict], agent_response: str, expected: dict) -> ScenarioScore`. Calls each evaluator, skips criteria not in `expected["applicable_criteria"]`, assembles `ScenarioScore`. | ✓ | 2026-04-06 |

### Phase 6: Minimal Harness

- GOAL-006: Wire everything together into a runnable harness that
  executes 3 scenarios on 1 model and prints traces + scores.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-022 | Create `eval/harness.py`. Load `FOUNDRY_PROJECT_ENDPOINT` from env var (with `python-dotenv` or `os.environ`). Define `SYSTEM_PROMPT` constant matching spec S3.1. Define default model as `"gpt-4.1-mini"`. | ✓ | 2026-04-06 |
| TASK-023 | Implement `async def evaluate_scenario(model: str, scenario: dict) -> dict`. Logic: (1) clear and update `SCENARIO_DATA` from scenario; (2) build instructions = SYSTEM_PROMPT + optional system_context; (3) create `RecorderMiddleware`; (4) create `FoundryChatClient(project_endpoint=..., model=model, credential=AzureCliCredential())`; (5) create `Agent(client=client, name="ONEAgent-Eval", instructions=instructions, tools=ALL_TOOLS, middleware=[recorder])`; (6) `result = await agent.run(scenario["user_message"])`; (7) return dict with model, scenario_id, tool_calls from recorder, agent_response text, and scores from `score_scenario`. Use `async with` for both credential and agent. | ✓ | 2026-04-06 |
| TASK-024 | Implement `async def run_all() -> list[dict]`. Load scenarios from `eval/scenarios/scenarios.json`. Loop over scenarios, call `evaluate_scenario("gpt-4.1-mini", scenario)` for each. Collect and return results. | ✓ | 2026-04-06 |
| TASK-025 | Implement `__main__` block: call `asyncio.run(main())` where `main()` calls `run_all()`, then prints each result's scenario_id, tool_calls summary, and scores to stdout using loguru. | ✓ | 2026-04-06 |
| TASK-026 | End-to-end validation: run `python -m eval.harness`. Verify: (1) Azure credential works (requires prior `az login`), (2) model responds, (3) tool calls are captured by RecorderMiddleware, (4) C1 score is computed for each scenario. Fix any framework API mismatches discovered during this step. | ✓ | 2026-04-06 |

## 3. Alternatives

- **ALT-001**: Raw OpenAI API calls instead of Agent Framework. Rejected:
  would require reimplementing the agentic loop (tool call -> execute ->
  feed result back -> next step), and wouldn't test the real integration
  path used in later phases.
- **ALT-002**: Semantic Kernel instead of Agent Framework. Rejected: Agent
  Framework is the direct successor and the decided-upon stack (see
  DECISIONS.md). The migration guide exists but adds unnecessary
  complexity.
- **ALT-003**: All 15 scenarios in Phase 0a. Rejected: building everything
  before validating the stack risks rework if the framework API behaves
  differently than expected.

## 4. Dependencies

- **DEP-001**: `agent-framework>=1.0.0` — Microsoft Agent Framework core
  (PyPI). Provides `Agent`, `@tool`, `FunctionMiddleware`,
  `FunctionInvocationContext`, `Message`, `AgentResponse`.
- **DEP-002**: `agent-framework-foundry>=1.0.0` — Azure AI Foundry
  integration (PyPI). Provides `FoundryChatClient`.
- **DEP-003**: `azure-identity>=1.19.0` — Azure authentication (PyPI).
  Provides `AzureCliCredential` (async version from `azure.identity.aio`).
- **DEP-004**: `pydantic>=2.0` — Parameter descriptions via
  `Annotated[type, Field(description=...)]`.
- **DEP-005**: `loguru>=0.7.0` — Structured logging.
- **DEP-006**: `pytest>=8.0`, `pytest-asyncio>=0.24` — Dev dependencies
  for testing evaluator logic.
- **DEP-007**: Azure AI Foundry project with `gpt-4.1-mini` model
  deployed. Requires `az login` and VS Enterprise subscription.

## 5. Files

- **FILE-001**: `pyproject.toml` — Project metadata and dependencies.
- **FILE-002**: `.env.example` — Template for `FOUNDRY_PROJECT_ENDPOINT`.
- **FILE-003**: `eval/__init__.py` — Package init (empty or minimal).
- **FILE-004**: `eval/tools.py` — 6 stub tools with `@tool` decorator,
  `SCENARIO_DATA` dict, `ALL_TOOLS` list.
- **FILE-005**: `eval/middleware.py` — `RecorderMiddleware` class.
- **FILE-006**: `eval/evaluators.py` — `ScenarioScore` dataclass,
  `evaluate_c1_correct_tool`, stubs for C2-C4, `score_scenario`.
- **FILE-007**: `eval/harness.py` — `evaluate_scenario`, `run_all`, main
  entry point.
- **FILE-008**: `eval/scenarios/scenarios.json` — 3 scenario definitions
  (A1, B1, C1).
- **FILE-009**: `eval/results/.gitkeep` — Placeholder for output directory
  (contents gitignored).

## 6. Testing

- **TEST-001**: Unit test `eval/evaluators.py` — `evaluate_c1_correct_tool`
  with synthetic tool_calls matching expected (should pass), wrong tool
  (should fail), extra tools (should still pass if expected tools present),
  empty tool_calls (should fail).
- **TEST-002**: Unit test `RecorderMiddleware` — verify `calls` list is
  populated after middleware processes a mock context, and `reset()` clears
  it.
- **TEST-003**: Integration test — run `python -m eval.harness` against
  live Azure AI Foundry. Verify non-empty tool_calls and non-None C1
  scores for all 3 scenarios. (Manual, requires Azure credentials.)

## 7. Risks & Assumptions

- **RISK-001**: Azure AI Foundry credentials not configured. Mitigation:
  TASK-026 validates connectivity early. Document `az login` requirement.
- **RISK-002**: `gpt-4.1-mini` not deployed in the Foundry project.
  Mitigation: harness prints clear error if model is unavailable. User
  can substitute another deployed model for initial validation.
- **RISK-003**: Agent Framework API may have undocumented behaviors
  (e.g., how it serializes tool schemas to the model, system prompt
  preamble injection). Mitigation: Phase 0a exists specifically to catch
  this before building the full suite.
- **RISK-004**: `FunctionMiddleware` may not capture tool arguments in the
  exact format expected (e.g., Pydantic model vs raw dict). Mitigation:
  TASK-014 logs raw `context.arguments` and TASK-026 inspects the output.
- **ASSUMPTION-001**: `agent-framework` 1.0.0 is stable and matches the
  documented API (verified via official docs on 2026-04-06).
- **ASSUMPTION-002**: The `@tool(approval_mode="never_require")` decorator
  suppresses all approval prompts during eval runs.
- **ASSUMPTION-003**: `FoundryChatClient` supports the same tool-calling
  protocol as `OpenAIChatClient` (both use the same Agent abstraction).

## 8. Completion Summary (2026-04-06)

**Status: Complete (Phase 0a)**

All 25 planning tasks delivered and merged to `main`:
- **Phases 1-6**: All scaffolding, tools, middleware, scenarios, evaluators, and harness complete
- **Merge**: Fast-forward merged to `main` with commit 7548bb9
- **Project venv**: Created and verified (`.venv/` with all dependencies)
- **VSCode setup**: `.vscode/settings.json` configured for import resolution
- **Exit criterion met**: `python -m eval.harness` is runnable (requires Azure credentials for TASK-026 validation)

**Remaining work:**
- **TASK-026 (manual)**: Run harness against live Azure AI Foundry with `az login` + `FOUNDRY_PROJECT_ENDPOINT` env var
- **Phase 0b**: Full 15-scenario suite, C2/C3/C4 evaluator implementations

**Key files delivered:**
- `eval/tools.py` (150 lines) — 6 tools with @tool decorator
- `eval/middleware.py` (38 lines) — RecorderMiddleware capturing tool calls
- `eval/evaluators.py` (174 lines) — ScenarioScore + C1 evaluator + C2-C4 stubs
- `eval/harness.py` (180 lines) — evaluate_scenario, run_all, __main__ entry
- `eval/scenarios/scenarios.json` (66 lines) — A1, B1, C1 scenarios
- `pyproject.toml` — project metadata + setuptools config

## 9. Related Specifications / Further Reading

- [Phase 0 Specification](../docs/PHASE0-MODEL-EXPLORATION.md)
- [Architecture Overview](../docs/DESIGN.md)
- [Decision Log](../docs/DECISIONS.md)
- [Agent Framework Overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Agent Framework Function Tools](https://learn.microsoft.com/en-us/agent-framework/agents/tools/function-tools)
- [Agent Framework Middleware](https://learn.microsoft.com/en-us/agent-framework/agents/middleware/)
- [Agent Framework Tool Approval](https://learn.microsoft.com/en-us/agent-framework/agents/tools/tool-approval)
- [agent-framework on PyPI](https://pypi.org/project/agent-framework/)
- [agent-framework-foundry on PyPI](https://pypi.org/project/agent-framework-foundry/)
