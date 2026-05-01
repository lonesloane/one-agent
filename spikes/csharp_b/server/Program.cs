// === Phase 2 verification (2026-05-01) ===
// API surface verified by reflection over installed NuGet assemblies
// (Microsoft.Agents.AI 1.3.0, Microsoft.Agents.AI.Foundry 1.3.0,
//  Microsoft.Extensions.AI.Abstractions 10.5.0, Azure.AI.Projects 2.0.0):
//
//   NOTE: Task spec references `FoundryChatClient` which does NOT exist in
//   Microsoft.Agents.AI.Foundry 1.3.0. The package ships `FoundryAgent` and the
//   `AzureAIProjectChatClientExtensions.AsAIAgent()` extension instead.
//   Path B (AIProjectClient + AsAIAgent extension) was chosen: builds with zero
//   warnings under TreatWarningsAsErrors=true, no OPENAI001 diagnostic, and
//   matches the Python two-step (client + agent) more closely.
//
//   Verified signatures:
//   AIProjectClient(Uri endpoint, AuthenticationTokenProvider credential)
//     — Azure.AI.Projects 2.0.0; AzureCliCredential is-a AuthenticationTokenProvider.
//
//   ChatClientAgent AIProjectClient.AsAIAgent(
//     string model, string instructions, string? name = null,
//     string? description = null, IList<AITool>? tools = null,
//     Func<IChatClient,IChatClient>? clientFactory = null,
//     ILoggerFactory? loggerFactory = null, IServiceProvider? services = null)
//     — extension method from Microsoft.Agents.AI.Foundry 1.3.0
//       (AzureAIProjectChatClientExtensions).
//
//   AIFunctionFactory.Create(Delegate method, AIFunctionFactoryOptions options)
//     — Microsoft.Extensions.AI.Abstractions 10.5.0.
//     Default name for PascalCase method: the description string passed to ctor
//     (or method name when no description). Override via options.Name = "snake_case"
//     to match parity instructions string (list_records / create_record).
//
//   ApprovalRequiredAIFunction(AIFunction innerFunction)
//     — Microsoft.Extensions.AI.Abstractions 10.5.0;
//       wraps innerFunction so the agent emits a ToolApprovalRequestContent
//       before executing.
//
//   AgentSession ChatClientAgent.CreateSessionAsync(CancellationToken)
//   AgentResponse ChatClientAgent.RunAsync(string message, AgentSession session,
//     AgentRunOptions? options, CancellationToken ct)
//   IAsyncEnumerable<AgentResponseUpdate> ChatClientAgent.RunStreamingAsync(
//     string message, AgentSession session, AgentRunOptions? options,
//     CancellationToken ct)
//     — both on ChatClientAgent (Microsoft.Agents.AI 1.3.0).
//
// === Phase 3 verification (2026-05-01) ===
// API surface verified by reflection + XML-doc over
// Microsoft.Agents.AI.Hosting.AGUI.AspNetCore 1.3.0-preview.260423.1:
//
//   MapAGUI overloads (extension class: AGUIEndpointRouteBuilderExtensions,
//   namespace: Microsoft.Agents.AI.Hosting.AGUI.AspNetCore):
//     IEndpointConventionBuilder MapAGUI(IEndpointRouteBuilder, IHostedAgentBuilder, string pattern)
//     IEndpointConventionBuilder MapAGUI(IEndpointRouteBuilder, string agentName, string pattern)
//     IEndpointConventionBuilder MapAGUI(IEndpointRouteBuilder, string pattern, AIAgent aiAgent)
//       <-- this is the overload used here (direct instance, no DI builder needed).
//
//   DI service registration:
//     IServiceCollection AddAGUI(IServiceCollection)
//       — MicrosoftAgentAIHostingAGUIServiceCollectionExtensions; registers
//         supporting serializer/SSE infrastructure used by the MapAGUI handler.
//
//   ** NO bidirectional approval middleware exists in this assembly. **
//   The plan's "UseAGUIApprovalAdapter" / "request_approval" synthetic tool name
//   are NOT present in Microsoft.Agents.AI.Hosting.AGUI.AspNetCore 1.3.0-preview.260423.1.
//   See RISK-001 note below.
//
//   Approval types (Microsoft.Extensions.AI.Abstractions, namespace Microsoft.Extensions.AI):
//     ToolApprovalRequestContent  — emitted by agent when ApprovalRequiredAIFunction is triggered.
//       Properties: ToolCallContent ToolCall, string RequestId
//       Method: ToolApprovalResponseContent CreateResponse(bool approved, string reason)
//     ToolApprovalResponseContent — returned by client to accept/reject the request.
//       Properties: bool Approved, ToolCallContent ToolCall, string Reason, string RequestId
//
//   RISK-001 (wire-contract delta): The plan spec assumed a `request_approval`
//   synthetic tool visible to the frontend. This name does NOT exist in the installed
//   assemblies. ApprovalRequiredAIFunction maps to an AGUITool under the WRAPPED
//   tool's name (e.g. "create_record"), not a synthetic approval name. AGUI event
//   types in this package: RUN_STARTED, RUN_FINISHED, RUN_ERROR, TEXT_MESSAGE_START,
//   TEXT_MESSAGE_CONTENT, TEXT_MESSAGE_END, TOOL_CALL_START, TOOL_CALL_ARGS,
//   TOOL_CALL_END, TOOL_CALL_RESULT, STATE_SNAPSHOT, STATE_DELTA. No APPROVAL event.
//
//   RISK-003 (multi-turn history sanitization): ProcessFunctionApprovalResponses lives
//   on PerServiceCallChatHistoryPersistingChatClient (Microsoft.Agents.AI), wired
//   internally by the MapAGUI handler. The handler strips ToolApprovalRequestContent
//   sentinel from ConversationId before forwarding to the model, so multi-turn 400s
//   should be prevented by the framework without additional middleware.
//
//   Phase 4 controller decision required:
//   REQ-001 / Phase 4 client must be updated — the frontend will receive a
//   TOOL_CALL_START event with name "create_record" (the real tool name), NOT
//   "request_approval". Phase 4 must either:
//   (a) handle the tool name directly, or
//   (b) introduce a wrapping adapter that re-emits under a synthetic name.

using Azure.AI.Projects;
using Azure.Identity;
using DotNetEnv;
using Microsoft.Agents.AI;
using Microsoft.Agents.AI.Hosting.AGUI.AspNetCore;
using Microsoft.Extensions.AI;
using SpikeServer.Logging;
using SpikeServer.Tools;

// Load .env at startup — mirrors Python's load_dotenv() in spikes/_shared/agent.py.
Env.Load();

string projectEndpoint = Environment.GetEnvironmentVariable("FOUNDRY_PROJECT_ENDPOINT")
    ?? throw new InvalidOperationException(
        "FOUNDRY_PROJECT_ENDPOINT is not set. Copy .env.example to .env and fill in the endpoint.");

// Tool-name decision: override to snake_case via AIFunctionFactoryOptions so the names
// match the parity instructions string verbatim (list_records / create_record).
AIFunction listRecordsFn = AIFunctionFactory.Create(
    RecordTools.ListRecords,
    new AIFunctionFactoryOptions
    {
        Name = "list_records",
        Description = "Return a comma-separated list of records.",
    });

AIFunction createRecordFn = AIFunctionFactory.Create(
    RecordTools.CreateRecord,
    new AIFunctionFactoryOptions
    {
        Name = "create_record",
        Description = "Create a new record with the given name.",
    });

// Gate create_record behind an approval step.
var approvalGatedCreateRecord = new ApprovalRequiredAIFunction(createRecordFn);

// Build the agent via AIProjectClient.AsAIAgent() (Path B).
// AzureCliCredential satisfies AuthenticationTokenProvider (same base class).
var projectClient = new AIProjectClient(
    new Uri(projectEndpoint),
    new AzureCliCredential());

ChatClientAgent agent = projectClient.AsAIAgent(
    model: "gpt-4.1-mini",
    instructions:
        "You assist a user managing a list of records. "
        + "Use list_records to read. "
        + "When the user asks to create a record and provides a name, "
        + "immediately call create_record with that name. "
        + "Do not ask for additional confirmation in chat — the "
        + "system handles approval through a separate mechanism.",
    name: "SpikeAgent",
    tools: [listRecordsFn, approvalGatedCreateRecord]);

var builder = WebApplication.CreateBuilder(args);

// AddAGUI registers supporting serializer/SSE infrastructure for the MapAGUI handler.
// Verified 2026-05-01 by reflection over Microsoft.Agents.AI.Hosting.AGUI.AspNetCore 1.3.0-preview.260423.1:
//   MicrosoftAgentAIHostingAGUIServiceCollectionExtensions.AddAGUI(IServiceCollection)
// This is the only DI registration the package provides. There is no UseAGUIApprovalAdapter.
builder.Services.AddAGUI();

builder.Services.AddSingleton(agent);

// Reason: no built-in tracing middleware exists in the AGUI package (verified by reflection:
// only 2 public types in Microsoft.Agents.AI.Hosting.AGUI.AspNetCore). Hand-rolling a thin
// request logger to satisfy TASK-017 diagnostic requirements.
builder.Services.AddSingleton<AGUIRequestLogger>();

var app = builder.Build();

// Log AG-UI endpoint requests before they reach the AGUI handler.
AGUIRequestLogger aguiLogger = app.Services.GetRequiredService<AGUIRequestLogger>();
app.Use(aguiLogger.LogRequestAsync);

// MapAGUI registers a POST handler at the given pattern.
// Verified 2026-05-01: overload signature is
//   IEndpointConventionBuilder MapAGUI(IEndpointRouteBuilder, string pattern, AIAgent aiAgent)
// Replaces the Phase 2 placeholder MapGet("/").
app.MapAGUI("/", agent);

app.Run();
