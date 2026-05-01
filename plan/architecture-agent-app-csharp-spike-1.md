---
goal: Step B — build the C# / .NET HITL spike under spikes/csharp_b/ and run T1–T4 against AG-UI to validate the 2026-04-29 stack pivot before scaffolding production agent_app/
version: 1.0
date_created: 2026-05-01
last_updated: 2026-05-01
owner: stephane.varin@gmail.com
status: 'Closed — Falsified (fall back to C4)'
tags: [architecture, spike, agent_app, dotnet, agent-framework, ag-ui]
---

# Introduction

![Status: Closed — Falsified](https://img.shields.io/badge/status-Closed%20--%20Falsified-red)

**Outcome (2026-05-01):** Phases 1–3 executed; Phases 4–5 not executed.
PAT-001 falsified by live SSE trace against the running spike server:
approval-gated tool calls produce no client-visible signal because
`Microsoft.Agents.AI.Hosting.AGUI.AspNetCore 1.3.0-preview.260423.1`
ships no approval-translation middleware (no `UseAGUIApprovalAdapter`,
no `request_approval` synthetic tool, no approval AGUI event type).
`MapAGUI` swallows `ToolApprovalRequestContent`. Non-approval flow
streams cleanly. Per-turn evidence + decision: `docs/research-agent-stack-candidates.md`
§5.5. Memory: `reference_dotnet_agui_hitl_broken.md`.

**Decision:** fall back to C4 (Chainlit + `agent-framework` Python)
for the PoC per the plan-opening escalation rule. Spike code retained
on `spike/csharp-b` for reference + re-evaluation when the AGUI
hosting package gap closes.

---

Step B of the agent-stack pivot decision (`docs/agent-stack-decision-2026-04-29.md` §7). Build a minimal C# / .NET spike under `spikes/csharp_b/` that runs the same four-turn HITL scenario the Python C4 (Chainlit) spike passed cleanly. Empirically falsifies — or confirms — that the documented .NET pattern (`Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` + `ApprovalRequiredAIFunction` + bidirectional middleware + `request_approval` synthetic client tool) round-trips approvals end-to-end. Spike is isolated from `agent_app/` deliberately (see ALT-001) — given prior HITL pain, a sibling-of-`c4_chainlit` layout keeps the falsification record clean. If the spike passes, production `agent_app/` is scaffolded fresh on a new branch off `main` and Step C (port `shared/business_rules.py`) follows. If it fails on something analogous to the Python C2 protocol issues, escalate before further investment — fall back to C4 (Chainlit) for the PoC.

## 1. Requirements & Constraints

- **REQ-001**: Spike must execute identical T1–T4 scenario as Python C4 spike — same tools (`ListRecords`, `CreateRecord`), same prompts, same model (`gpt-4.1-mini`).
- **REQ-002**: Use `gpt-4.1-mini` via `FoundryChatClient` (.NET equivalent: `Microsoft.Agents.AI.Foundry` + `AsAIAgent` extension) — no model swap during spike.
- **REQ-003**: Auth via `AzureCliCredential` (mirrors C4 spike, no secret management).
- **REQ-004**: HITL via `ApprovalRequiredAIFunction` wrapping `CreateRecord`; bidirectional middleware emits `request_approval` synthetic tool calls to client and translates approval responses back into agent-framework `FunctionApprovalResponseContent`.
- **REQ-005**: AG-UI server mounted via `app.MapAGUI("/", agent)`; spike client is the console `AGUIChatClient` from MS Learn .NET getting-started, extended to detect `FunctionApprovalRequestContent` and prompt approve/deny.
- **REQ-006**: Pass criterion — T1 streams "alpha, beta"; T2 emits approval prompt → approve → tool fires; T3 emits approval prompt → deny → agent acknowledges, no orphan tool_call, no 400; T4 lists `alpha, beta, gamma` (gamma from T2 success, delta absent from T3 denial). Identical outcome to C4 spike.
- **REQ-007**: Total spike effort ≤ 1 working day per decision doc Step B budget.
- **SEC-001**: No secrets in code or repo; rely on `az login` session for `AzureCliCredential`.
- **CON-001**: Hand-written code budget ≤ 250 LOC across server + client (tooling/boilerplate excluded).
- **CON-002**: No real DB, no real auth, no real identity threading. In-memory `_records` list mirroring `spikes/_shared/agent.py` only.
- **CON-003**: Target framework .NET 8 (LTS) — pinned in `spikes/csharp_b/server/SpikeServer.csproj` `<TargetFramework>net8.0</TargetFramework>`. Bump to .NET 9 deferred unless an Agent Framework package requires it.
- **CON-004**: Project conventions per `.claude/CLAUDE.md` C# section — `<Nullable>enable</Nullable>`, `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`, file-scoped namespaces, `dotnet format` clean before commit.
- **GUD-001**: Before writing any code touching Microsoft Agent Framework APIs, query Context7 (`/websites/learn_microsoft_en-us_agent-framework`) with `?pivots=programming-language-csharp` URLs only — Python pattern leakage caused the Python C2 spike confusion (see decision doc §4).
- **GUD-002**: Match C4 Chainlit spike's `Agent.instructions` verbatim where shape allows (already model-tested): "You assist a user managing records. Use list_records for reads. Use create_record only when the user explicitly asks to create. Call the tool immediately and let the system handle approval."
- **PAT-001**: Bidirectional middleware pattern — client→server: translate `request_approval` synthetic tool result into `FunctionApprovalResponseContent`; server→client: translate `FunctionApprovalRequestContent` into a `request_approval` synthetic tool call. Reference: MS Learn HITL .NET zone.
- **PAT-002**: Spike code lives on `research/agent-stack-spikes` branch under `spikes/csharp_b/` — sibling to existing `spikes/c2_custom_agui/` and `spikes/c4_chainlit/` Python spikes. Spike is throwaway by default; on pass, the production `agent_app/` C# scaffold is created fresh on a new branch off `main` reusing the validated patterns (not `git mv`-ed from `spikes/`). Keeps falsification record intact and avoids carrying spike-only shortcuts (in-memory store, console client, hardcoded port) into production code.

## 2. Implementation Steps

### Implementation Phase 1 — .NET project scaffold

- GOAL-001: Create the `spikes/csharp_b/server/` C# project with correct SDK, target framework, NuGet references, and conventions wired so a `dotnet build` succeeds before any spike code is written.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-001 | Verify .NET SDK installed: `dotnet --list-sdks` shows 8.0.x or 9.0.x. If absent, install .NET 8 LTS SDK via official channel. | ✅ | 2026-05-01 |
| TASK-002 | Create directory `spikes/csharp_b/`. From `spikes/csharp_b/` run `dotnet new web -n SpikeServer -o server --framework net8.0`. Result: `spikes/csharp_b/server/SpikeServer.csproj`, `spikes/csharp_b/server/Program.cs`, `spikes/csharp_b/server/appsettings.json`, `spikes/csharp_b/server/Properties/launchSettings.json`. | ✅ | 2026-05-01 |
| TASK-003 | Edit `spikes/csharp_b/server/SpikeServer.csproj` — set `<Nullable>enable</Nullable>`, `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>`, `<ImplicitUsings>enable</ImplicitUsings>`, `<LangVersion>latest</LangVersion>`. | ✅ | 2026-05-01 |
| TASK-004 | Add `spikes/csharp_b/global.json` pinning the SDK roll-forward policy: `{ "sdk": { "version": "8.0.0", "rollForward": "latestFeature" } }`. | ✅ | 2026-05-01 |
| TASK-005 | Add `.editorconfig` at repo root (or extend existing) with `dotnet_naming_*` rules: PascalCase types/methods, _camelCase private fields, file-scoped namespaces. Verify `dotnet format --verify-no-changes` passes on the empty scaffold. | ✅ | 2026-05-01 |
| TASK-006 | Add NuGet packages to `SpikeServer.csproj` via `dotnet add spikes/csharp_b/server package <name>`: `Microsoft.Agents.AI` (latest preview), `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` (latest preview), `Microsoft.Agents.AI.Foundry` (latest preview), `Azure.Identity` (stable). Pin versions explicitly — no floating refs. | ✅ | 2026-05-01 |
| TASK-007 | Add `spikes/csharp_b/.gitignore` entries: `bin/`, `obj/`, `*.user`, `appsettings.Development.json`. Verify build output is not staged. | ✅ | 2026-05-01 |
| TASK-008 | Verify clean build: `dotnet build spikes/csharp_b/server/SpikeServer.csproj` returns exit 0, zero warnings. | ✅ | 2026-05-01 |

### Implementation Phase 2 — Agent + tools (server-side)

- GOAL-002: Build the in-memory record agent with `ListRecords` (no approval) and `CreateRecord` (wrapped in `ApprovalRequiredAIFunction`), wired to `gpt-4.1-mini` via Azure AI Foundry. No HTTP surface yet.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-009 | Context7 query: `/websites/learn_microsoft_en-us_agent-framework` with topic "AIAgent Foundry AsAIAgent" — capture exact `AIAgent` factory signature for Foundry + `AzureCliCredential` wiring. Record findings as comments in `spikes/csharp_b/server/Program.cs` for reviewer audit. | ✅ | 2026-05-01 |
| TASK-010 | Create `spikes/csharp_b/server/Tools/RecordStore.cs` — static class holding `private static readonly List<string> _records = new() { "alpha", "beta" };`. Methods: `IReadOnlyList<string> List()` and `int Add(string name)` returning new total count. Thread-safety not required for spike (single-threaded request flow). | ✅ | 2026-05-01 |
| TASK-011 | Create `spikes/csharp_b/server/Tools/RecordTools.cs` — two methods decorated for Agent Framework tool registration: `[Description("Return a comma-separated list of records.")] public static string ListRecords()` and `[Description("Create a new record with the given name.")] public static string CreateRecord([Description("Name of the record to create")] string name)`. Verify the exact decorator (`[AIFunction]`, `[Description]`, `[McpServerTool]`, etc.) via Context7 before writing. | ✅ | 2026-05-01 |
| TASK-012 | In `spikes/csharp_b/server/Program.cs` build the agent: load `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_CHAT_COMPLETION_MODEL` (= `gpt-4.1-mini`), `AZURE_OPENAI_API_VERSION` from environment / appsettings. Construct `FoundryChatClient` with `AzureCliCredential`. Construct `AIAgent` with name `SpikeAgent`, instructions verbatim from GUD-002, tools = [`ListRecords` AIFunction, `CreateRecord` wrapped via `ApprovalRequiredAIFunction.Wrap(createRecordFn)` or equivalent helper]. | ✅ | 2026-05-01 |
| TASK-013 | Verify agent boots in isolation via a temporary `Main` smoke call: invoke `agent.RunAsync("List the records")` and write the streamed response to console. Pass: streams "alpha, beta". Remove the smoke call once verified. | ✅ | 2026-05-01 |

### Implementation Phase 3 — AG-UI server endpoint + bidirectional middleware

- GOAL-003: Mount the agent at `/` via `app.MapAGUI` and install the bidirectional middleware that translates `FunctionApprovalRequestContent` ↔ `request_approval` synthetic tool messages on the wire.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-014 | Context7 query: same library, topic "MapAGUI ApprovalRequiredAIFunction request_approval middleware HITL" with `?pivots=programming-language-csharp` — capture exact middleware registration API and the synthetic tool-name constant. Confirm `request_approval` is the correct synthetic name (vs Python's `confirm_changes` per decision doc §3.2). | ✅ | 2026-05-01 |
| TASK-015 | In `spikes/csharp_b/server/Program.cs` after agent construction: `app.MapAGUI("/", agent)`. Verify the AG-UI handler is registered by hitting `GET /` with `Accept: text/event-stream` via curl — expect 200 + SSE upgrade or method-not-allowed (POST-only) response, not 404. | ✅ | 2026-05-01 |
| TASK-016 | Add bidirectional middleware: install the documented `.NET` HITL adapter so server-emitted `FunctionApprovalRequestContent` becomes a client-visible `request_approval` tool call, and a client-side `request_approval` tool result becomes server-side `FunctionApprovalResponseContent`. Use the exact registration call from MS Learn (likely `app.UseAGUIApprovalAdapter()` or builder-method equivalent — verify via Context7 in TASK-014). | ✅ | 2026-05-01 |
| TASK-017 | Add structured request/response logging via `ILogger` at the AG-UI handler boundary — log each AG-UI event type, tool call, and approval response. Sufficient detail to diagnose F1 (approval not rendered) or F2 (multi-turn 400) symptoms during T1–T4 walk-through. | ✅ | 2026-05-01 |
| TASK-018 | Run `dotnet run --project spikes/csharp_b/server/SpikeServer.csproj` and confirm server listens on `http://localhost:5000` (or whichever port `launchSettings.json` assigns). Capture chosen port in plan notes for client-side spike. | ✅ | 2026-05-01 |

### Implementation Phase 4 — Spike client (console)

- GOAL-004: Build a throwaway console client that connects to the AG-UI server, drives T1–T4, prompts approve/deny on `FunctionApprovalRequestContent`, and prints streamed text + tool results.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-019 | From `spikes/csharp_b/` run `dotnet new console -n SpikeClient -o client --framework net8.0`. Result: `spikes/csharp_b/client/SpikeClient.csproj`, `spikes/csharp_b/client/Program.cs`. Apply same nullable + warnings-as-errors flags as TASK-003. NuGet ref: `Microsoft.Agents.AI` + `Microsoft.Agents.AI.Hosting.AGUI` (client portion exposing `AGUIChatClient`). | | |
| TASK-020 | Context7 query: same library, topic "AGUIChatClient endpoint console client" with `?pivots=programming-language-csharp` — capture exact constructor signature. Confirm endpoint kwarg name (was `endpoint=` in Python per decision doc §4 — verify .NET equivalent). | | |
| TASK-021 | Implement `spikes/csharp_b/client/Program.cs`: instantiate `AGUIChatClient` pointing at `http://localhost:5000/`. Loop reading lines from stdin, send each as a user message, stream agent response chunks to stdout. On `FunctionApprovalRequestContent` (or `request_approval` synthetic tool call), pause stream, print "Approve `<tool>(<args>)`? [y/n]", read stdin, send `FunctionApprovalResponseContent` with `Approved=true|false` back to server, resume stream. | | |
| TASK-022 | Verify client build: `dotnet build` exit 0, zero warnings. Verify client connects and exchanges one trivial turn ("hello") with the server before driving the full T1–T4 scenario. | | |

### Implementation Phase 5 — Run T1–T4 and record verdict

- GOAL-005: Execute the four-turn scenario manually, document outcomes per turn against pass criteria, and write the spike result section into `docs/research-agent-stack-candidates.md`. Decide pivot validation outcome.

| Task | Description | Completed | Date |
|------|-------------|-----------|------|
| TASK-023 | Start server: `dotnet run --project spikes/csharp_b/server/SpikeServer.csproj`. Start client in second terminal: `dotnet run --project spikes/csharp_b/client/SpikeClient.csproj`. | | |
| TASK-024 | T1 — type "List the records". Expected: `ListRecords` invoked, stream prints "alpha, beta". Record pass/fail + raw stream excerpt + server-side log excerpt. | | |
| TASK-025 | T2 — type "Create a record named gamma". Expected: approval prompt shown, type `y`, agent reports gamma created. Record pass/fail + approval-prompt rendering + tool-result content. | | |
| TASK-026 | T3 — type "Create another one named delta". Expected: approval prompt shown, type `n`, agent acknowledges denial in natural language, no orphan `tool_call`, no 400 from OpenAI on next turn. Record pass/fail. This is the F2 watch-point. | | |
| TASK-027 | T4 — type "List the records again". Expected: `ListRecords` invoked, stream contains `alpha, beta, gamma` (gamma from T2 success); does NOT contain `delta`. Record pass/fail + raw stream excerpt. | | |
| TASK-028 | Append `## §5.3 Spike Step B (C# .NET) — <PASS \| FAIL>` section to `docs/research-agent-stack-candidates.md` with: per-turn pass/fail table, two-sentence narrative on what surprised us, declarative outcome ("C# pivot validated, proceed to Step C" or "C# pivot blocked on <symptom>, escalate"). | | |
| TASK-029 | Update `docs/agent-stack-decision-2026-04-29.md` Status section (or add a Step B closure paragraph) with verdict + commit SHA of the spike scaffold. Update `MEMORY.md` pivot entry with Step B outcome. | | |
| TASK-030 | Run `dotnet format spikes/csharp_b/`. Verify clean. Run `dotnet build spikes/csharp_b/server/SpikeServer.csproj` and `dotnet build spikes/csharp_b/client/SpikeClient.csproj` — both exit 0, zero warnings. Commit scaffold + spike result onto `research/agent-stack-spikes` branch (do NOT merge to main yet). On pass, follow-up work scaffolds the production `agent_app/` C# project fresh on a new branch off `main` — do not `git mv` `spikes/csharp_b/` into `agent_app/`. | | |

## 3. Alternatives

- **ALT-001**: Scaffold directly at `agent_app/` root rather than under `spikes/csharp_b/`. Rejected 2026-05-01: history of HITL contract failures (Python C2 spike + abandoned Phase 3/4 attempt) raises the prior on .NET path also surprising us. Isolating the spike under `spikes/` keeps falsification record intact, mirrors the existing Python spike layout (`spikes/c2_custom_agui/`, `spikes/c4_chainlit/`), and on pass forces a clean re-scaffold for production that strips spike shortcuts (in-memory store, console client, hardcoded port, no DB / auth / identity threading) instead of carrying them forward via `git mv`.
- **ALT-002**: Bypass `ApprovalRequiredAIFunction` and roll a custom server-side approval gate. Rejected: defeats the purpose of the spike — REQ-006 is to validate the *documented* .NET HITL pattern works. A custom gate would prove only that we can write a custom gate.
- **ALT-003**: Use a lightweight Blazor or React client instead of a console client. Rejected: console isolates the AG-UI / approval contract from frontend rendering complexity. CopilotKit React lands in Step D PRDs once the wire-level contract is empirically green.
- **ALT-004**: Target .NET 9 instead of .NET 8. Rejected for spike: LTS preferred unless a required Agent Framework package only ships .NET 9. If TASK-006 reveals a .NET 9 floor, bump CON-003 and proceed.
- **ALT-005**: Skip the spike, scaffold + port + PRD all at once. Rejected: explicitly the failure mode of the abandoned Python attempt — building production-grade plumbing on an unverified HITL contract. Spike-then-build is the correction.

## 4. Dependencies

- **DEP-001**: .NET 8 LTS SDK (or .NET 9) installed locally; `dotnet --list-sdks` confirms.
- **DEP-002**: `Microsoft.Agents.AI` NuGet package (latest preview as of 2026-05-01).
- **DEP-003**: `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` NuGet package — server-side AG-UI host.
- **DEP-004**: `Microsoft.Agents.AI.Foundry` NuGet package — `FoundryChatClient` + `AsAIAgent` extension.
- **DEP-005**: `Azure.Identity` NuGet (stable) — `AzureCliCredential`.
- **DEP-006**: Active `az login` session with access to the Foundry endpoint hosting `gpt-4.1-mini`.
- **DEP-007**: Environment variables in `.env` or shell: `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_CHAT_COMPLETION_MODEL=gpt-4.1-mini`, `AZURE_OPENAI_API_VERSION` (matches Python spike's `.env`).
- **DEP-008**: Context7 MCP server reachable for `/websites/learn_microsoft_en-us_agent-framework` queries (TASK-009, TASK-014, TASK-020).
- **DEP-009**: C4 Chainlit spike artifacts under `spikes/c4_chainlit/` retained as parity reference.

## 5. Files

- **FILE-001**: `spikes/csharp_b/server/SpikeServer.csproj` — server project file, target framework, NuGet refs, conventions.
- **FILE-002**: `spikes/csharp_b/server/Program.cs` — server bootstrap: agent construction, `MapAGUI("/", agent)`, middleware registration, logging.
- **FILE-003**: `spikes/csharp_b/server/Tools/RecordStore.cs` — in-memory record list (alpha/beta seed + `Add`).
- **FILE-004**: `spikes/csharp_b/server/Tools/RecordTools.cs` — `ListRecords` + `CreateRecord` AIFunctions w/ `[Description]` decorators.
- **FILE-005**: `spikes/csharp_b/global.json` — SDK pin (covers both server + client projects under the dir).
- **FILE-006**: `spikes/csharp_b/server/appsettings.json` — non-secret config (port, log levels). Secrets via env vars only.
- **FILE-007**: `spikes/csharp_b/client/SpikeClient.csproj` — console spike client project.
- **FILE-008**: `spikes/csharp_b/client/Program.cs` — `AGUIChatClient` console driver with approve/deny stdin prompt.
- **FILE-009**: `.editorconfig` (repo root, new or extended) — C# style rules consumed by `dotnet format`.
- **FILE-010**: `spikes/csharp_b/.gitignore` — `bin/`, `obj/`, `*.user`, `appsettings.Development.json`.
- **FILE-011**: `docs/research-agent-stack-candidates.md` — append `§5.3 Spike Step B` section with verdict.
- **FILE-012**: `docs/agent-stack-decision-2026-04-29.md` — append Step B closure paragraph in §7.
- **FILE-013**: `MEMORY.md` + `project_agent_stack_pivot.md` — Step B outcome row.

## 6. Testing

- **TEST-001**: T1 turn-level pass — `ListRecords` invoked exactly once, response stream contains "alpha, beta". Manual stdout inspection + server log assertion. (TASK-024.)
- **TEST-002**: T2 approval-rendered + approve-path-fires — `FunctionApprovalRequestContent` (or `request_approval` synthetic) reaches client; approve response routes back; `CreateRecord(name="gamma")` fires; response stream confirms creation. (TASK-025.)
- **TEST-003**: T3 deny-path-clean — approval prompt rendered; deny response routes back; no orphan tool_call in subsequent turn; no HTTP 400 from OpenAI on T4 invocation. (TASK-026.) F2 watch-point.
- **TEST-004**: T4 multi-turn-history-valid — `ListRecords` invoked; stream lists `alpha, beta, gamma`; does NOT include `delta`. (TASK-027.) Confirms server-side history sanitization removed denied-approval orphan correctly.
- **TEST-005**: Build green — `dotnet build` on both projects exits 0, zero warnings, zero errors.
- **TEST-006**: Format clean — `dotnet format --verify-no-changes` passes on `spikes/csharp_b/`.
- **TEST-007**: Parity-with-C4 — verdict narrative explicitly compares Step B per-turn outcomes against C4 spike per-turn outcomes; any divergence is documented as a finding.

## 7. Risks & Assumptions

- **RISK-001**: `ApprovalRequiredAIFunction` API surface or the bidirectional middleware registration call may have shifted in a recent preview release. Mitigation: Context7 queries in TASK-009/014/020 verify against current docs before writing code; pin NuGet versions explicitly (TASK-006).
- **RISK-002**: `AGUIChatClient` console client may not surface `FunctionApprovalRequestContent` through the documented stream type, mirroring the Python C2 finding. Mitigation: TEST-003 explicitly tests this; if client cannot detect approval requests, log the raw chunk types and inspect — same diagnostic path Python C2 took.
- **RISK-003**: F2 (multi-turn 400) reproducible on .NET via the same root cause — server-side history not stripping `request_approval` entries. Mitigation: documented .NET pattern explicitly handles this server-side; if it does not, this is the falsification we wanted and we escalate to C4 fallback.
- **RISK-004**: Foundry endpoint or `gpt-4.1-mini` deployment unavailable during spike. Mitigation: pre-flight TASK-013 smoke call validates auth + model before the AG-UI surface adds variables; failure here points at infra not stack.
- **RISK-005**: `dotnet new web` default project structure conflicts with `<Nullable>enable</Nullable>` + `<TreatWarningsAsErrors>true</TreatWarningsAsErrors>` in scaffold (boilerplate may have warnings). Mitigation: TASK-008 build verification catches this; fix template warnings before adding spike code.
- **RISK-006**: MS Learn .NET zone documentation gaps (analogous to the Python sample's structural bugs per decision doc §4). Mitigation: Context7 cross-checks against installed package introspection (`dotnet symbol-search` or reflection in a probe program) before relying on a documented API.
- **ASSUMPTION-001**: `gpt-4.1-mini` retains its Phase 0f-validated tool-selection quality on the C# `AIAgent` runtime — model is the same; only the orchestration runtime changes.
- **ASSUMPTION-002**: `Agent.instructions` accepts the same string verbatim across runtimes (already model-tested via C4 spike).
- **ASSUMPTION-003**: `azure-identity` `AzureCliCredential` works equivalently in C# (`Azure.Identity.AzureCliCredential`) — well-documented parity surface.
- **ASSUMPTION-004**: Spike runs on the user's local laptop with `az login` already active. Headless / CI execution is out of scope.

## 8. Related Specifications / Further Reading

- `docs/agent-stack-decision-2026-04-29.md` — pivot decision record (§7 Step B is the source for this plan).
- `docs/research-agent-stack-candidates.md` — candidate survey + Python spike results (§3 / §5).
- `plan/research-agent-stack-spike.md` — Python spike plan (T1–T4 scenario definition reused here).
- `spikes/c4_chainlit/app.py` — passing Python spike kept as parity reference.
- `spikes/c2_custom_agui/` — falsification record for the Python AG-UI client; informs RISK-002 and RISK-003.
- `.claude/CLAUDE.md` — C# / .NET conventions (target framework, nullable, `dotnet format`, `Async` suffix).
- Microsoft Agent Framework .NET docs via Context7 ID `/websites/learn_microsoft_en-us_agent-framework` — always with `?pivots=programming-language-csharp`.
- CopilotKit MAF docs — out of scope for Step B; arrives in Step D PRDs.
