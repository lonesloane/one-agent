"use client";

import { useState } from "react";
import {
  CopilotChat,
  useDefaultRenderTool,
} from "@copilotkit/react-core/v2";
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

function ChatPane({ threadId }: { threadId: string }) {
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

  return (
    <CopilotChat
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
        <ChatPane threadId={threadId} />
      )}
    </div>
  );
}
