---
name: MAF 1.3.0 C# API surface (verified by reflection 2026-05-01)
description: Actual API for agent construction in Microsoft.Agents.AI 1.3.0 — FoundryChatClient does not exist
type: reference
---

## Critical finding: `FoundryChatClient` does NOT exist in 1.3.0

The CLAUDE.md and plan docs reference `FoundryChatClient` as the construction path.
This type is NOT present in `Microsoft.Agents.AI.Foundry 1.3.0`. The package ships
`FoundryAgent` (marked OPENAI001 experimental) and the `AsAIAgent()` extension instead.

## Recommended construction path (Path B — zero warnings)

```csharp
// 1. Build AIProjectClient (Azure.AI.Projects 2.0.0)
var client = new AIProjectClient(
    new Uri(projectEndpoint),   // FOUNDRY_PROJECT_ENDPOINT
    new AzureCliCredential());  // AzureCliCredential is-a AuthenticationTokenProvider

// 2. Create ChatClientAgent via extension from Microsoft.Agents.AI.Foundry
ChatClientAgent agent = client.AsAIAgent(
    model: "gpt-4.1-mini",
    instructions: "...",
    name: "SpikeAgent",
    tools: [listFn, approvalWrappedFn]);
```

This builds with `TreatWarningsAsErrors=true` and zero warnings.
`FoundryAgent` constructor triggers `OPENAI001` diagnostic and must be suppressed.

## Tool registration pattern

```csharp
// Use AIFunctionFactory.Create with AIFunctionFactoryOptions to control name
AIFunction fn = AIFunctionFactory.Create(
    RecordTools.ListRecords,
    new AIFunctionFactoryOptions { Name = "list_records", Description = "..." });

// Gate with approval
var gated = new ApprovalRequiredAIFunction(fn);
```

`AIFunctionFactory` and `ApprovalRequiredAIFunction` are in
`Microsoft.Extensions.AI.Abstractions 10.5.0` (NOT in Microsoft.Agents.AI).

Default tool name from `AIFunctionFactory.Create(method, description)` is the
description string. Use `AIFunctionFactoryOptions.Name` to override to snake_case.

## Session + run pattern

```csharp
AgentSession session = await agent.CreateSessionAsync();

// Non-streaming
AgentResponse response = await agent.RunAsync("message", session, options: null);
Console.WriteLine(response.Text);

// Streaming  
await foreach (AgentResponseUpdate update in agent.RunStreamingAsync("message", session, options: null))
    Console.Write(update.Text);
```

All RunAsync/RunStreamingAsync overloads require an `AgentSession` parameter — no session-less convenience overload exists.

## Phase 3: AGUI hosting package surface (verified 2026-05-01)

Package: `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore 1.3.0-preview.260423.1`
Only 2 public types:
- `AGUIEndpointRouteBuilderExtensions` — 3 `MapAGUI` overloads
- `MicrosoftAgentAIHostingAGUIServiceCollectionExtensions` — `AddAGUI(IServiceCollection)`

### MapAGUI overloads

```csharp
// Overload 1: using IHostedAgentBuilder (DI builder pattern)
IEndpointConventionBuilder MapAGUI(IEndpointRouteBuilder, IHostedAgentBuilder agentBuilder, string pattern)

// Overload 2: using named keyed DI registration
IEndpointConventionBuilder MapAGUI(IEndpointRouteBuilder, string agentName, string pattern)

// Overload 3: direct instance (used in spike)
IEndpointConventionBuilder MapAGUI(IEndpointRouteBuilder, string pattern, AIAgent aiAgent)
```

### DI registration

```csharp
builder.Services.AddAGUI();  // registers SSE/serializer infrastructure
```

### CRITICAL: No bidirectional approval middleware

`UseAGUIApprovalAdapter` DOES NOT EXIST in this package.
`request_approval` synthetic tool name DOES NOT EXIST.
The plan's "bidirectional middleware" model is incorrect.

Actual approval flow:
- `ApprovalRequiredAIFunction` wraps `create_record` and maps to an `AGUITool` under
  the REAL tool's name (`create_record`), not a synthetic approval name.
- The `MapAGUI` handler closure uses `FilterServerToolsFromMixedToolInvocationsAsync`
  to split client vs server tools inline — no separate middleware step.
- `ProcessFunctionApprovalResponses` is wired internally in `PerServiceCallChatHistoryPersistingChatClient`.
- AGUI event types: RUN_STARTED, RUN_FINISHED, RUN_ERROR, TEXT_MESSAGE_*, TOOL_CALL_* , STATE_*
  — NO APPROVAL event type.

### Approval content types (Microsoft.Extensions.AI.Abstractions)

```csharp
// Emitted by agent when ApprovalRequiredAIFunction tool is called
Microsoft.Extensions.AI.ToolApprovalRequestContent
  // Properties: ToolCallContent ToolCall, string RequestId
  // Method: ToolApprovalResponseContent CreateResponse(bool approved, string reason)

// Client sends back to accept/reject
Microsoft.Extensions.AI.ToolApprovalResponseContent
  // Properties: bool Approved, ToolCallContent ToolCall, string Reason, string RequestId
```

### Phase 4 wire-contract impact

Phase 4 client will see `TOOL_CALL_START` with name `create_record` (the wrapped tool's name),
NOT `request_approval`. REQ-001 requires controller decision before Phase 4 implementation:
(a) handle `create_record` tool call directly as the approval trigger, or
(b) interpose a hand-written adapter to re-emit under a synthetic approval name.

### AGUI MapAGUI handler is POST-only

`MapAGUI` registers a POST endpoint. `GET /` returns `405 Method Not Allowed` with `Allow: POST`.
Confirmed by curl smoke test (TASK-018, 2026-05-01, port 5141).

## Package versions (verified 2026-05-01)

- `Microsoft.Agents.AI` 1.3.0 — stable
- `Microsoft.Agents.AI.Foundry` 1.3.0 — stable but `FoundryAgent` is OPENAI001 experimental
- `Microsoft.Agents.AI.Hosting.AGUI.AspNetCore` 1.3.0-preview.260423.1 — 2 public types only
- `Microsoft.Extensions.AI.Abstractions` 10.5.0 — contains `AIFunctionFactory`, `ApprovalRequiredAIFunction`, `ToolApprovalRequestContent`, `ToolApprovalResponseContent`
- `Azure.AI.Projects` 2.0.0 — `AIProjectClient(Uri, AuthenticationTokenProvider)`
