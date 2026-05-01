// API surface verified 2026-05-01 by reflection over installed NuGet assemblies
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

using Azure.AI.Projects;
using Azure.Identity;
using DotNetEnv;
using Microsoft.Agents.AI;
using Microsoft.Extensions.AI;
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

builder.Services.AddSingleton(agent);

var app = builder.Build();

app.MapGet("/", () => "SpikeServer running — Phase 2 agent wired, HTTP endpoints Phase 3.");

app.Run();
