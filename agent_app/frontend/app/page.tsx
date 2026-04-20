"use client";

import { useEffect, useState } from "react";
import {
  CopilotChat,
  useAgent,
  useCopilotKit,
  useDefaultRenderTool,
} from "@copilotkit/react-core/v2";
import { CopilotKitCoreRuntimeConnectionStatus } from "@copilotkit/core";
import "@copilotkit/react-core/v2/styles.css";
import { DelegatePicker } from "./components/DelegatePicker";

function ToolCallBlock({
  name,
  status,
  parameters,
  result,
}: {
  name: string;
  status: "inProgress" | "executing" | "complete";
  parameters: unknown;
  result: string | undefined;
}) {
  const label =
    status === "complete" ? `\u2713 ${name}` : `\u23f3 ${name}`;
  return (
    <details style={{ fontSize: "0.85em", margin: "4px 0" }}>
      <summary style={{ cursor: "pointer" }}>{label} [{status}]</summary>
      <pre style={{ margin: "4px 0 0 12px", whiteSpace: "pre-wrap" }}>
        {JSON.stringify(parameters, null, 2)}
      </pre>
      {status === "complete" && result !== undefined && (
        <pre style={{ margin: "4px 0 0 12px", whiteSpace: "pre-wrap" }}>
          Result: {result}
        </pre>
      )}
    </details>
  );
}

function ChatPane({
  threadId,
  delegateId,
}: {
  threadId: string;
  delegateId: string;
}) {
  // Reason: when threadId is passed, useAgent returns a per-thread
  // clone from a global WeakMap; without it, the shared registry agent.
  // CopilotChat (threadId={threadId}) always resolves to the per-thread
  // clone. If this hook is called without threadId, it returns a
  // *different instance* than the chat — runAgent appends messages to
  // the registry agent and the chat view stays empty.
  const { agent } = useAgent<{ delegate_id: string }>({
    agentId: "ONEMPReadAgent",
    threadId,
    initialState: { delegate_id: "" },
  });
  const { copilotkit } = useCopilotKit();

  useDefaultRenderTool({
    render: ({ name, status, parameters, result }) => (
      <ToolCallBlock
        name={name}
        status={status}
        parameters={parameters}
        result={result}
      />
    ),
  });

  useEffect(() => {
    // Reason: while the runtime is still Connecting, useAgent returns a
    // ProxiedCopilotRuntimeAgent (provisional). Firing runAgent on that
    // provisional instance invisibly no-ops — CopilotChat later rebinds
    // to the real per-thread clone and the chat view stays empty. Gate
    // the fire on Connected status AND re-run when agent identity flips
    // (provisional → real clone) so the closure captures the live agent.
    // The "start" message is required: run_agent_stream short-circuits
    // on empty messages without calling the LLM. CopilotChat fires its
    // own /connect on mount; the short setTimeout lets that settle before
    // our runAgent to avoid "Thread already running".
    if (copilotkit.runtimeConnectionStatus !==
        CopilotKitCoreRuntimeConnectionStatus.Connected) {
      return;
    }
    const timer = setTimeout(async () => {
      agent.setState({ delegate_id: delegateId });
      agent.addMessage({
        id: crypto.randomUUID(),
        role: "user",
        content: "start",
      });
      await copilotkit.runAgent({ agent });
    }, 500);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [threadId, delegateId, agent, copilotkit.runtimeConnectionStatus]);

  return (
    <CopilotChat
      agentId="ONEMPReadAgent"
      threadId={threadId}
      style={{ flex: 1, minHeight: 0 }}
    />
  );
}

export default function Home() {
  const [threadId, setThreadId] = useState<string>(
    () => crypto.randomUUID(),
  );
  const [selectedDelegateId, setSelectedDelegateId] =
    useState<string>("");

  function handleDelegateChange(id: string): void {
    setSelectedDelegateId(id);
  }

  function handleThreadReset(): void {
    setThreadId(crypto.randomUUID());
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100vh",
      }}
    >
      <div style={{ padding: "8px 16px", borderBottom: "1px solid #ddd" }}>
        <DelegatePicker
          onDelegateChange={handleDelegateChange}
          onThreadReset={handleThreadReset}
        />
      </div>
      {selectedDelegateId !== "" && (
        <ChatPane threadId={threadId} delegateId={selectedDelegateId} />
      )}
    </div>
  );
}
