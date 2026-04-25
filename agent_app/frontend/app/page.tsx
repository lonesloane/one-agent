"use client";

import { useEffect, useState } from "react";
import {
  CopilotChat,
  useAgent,
  useCopilotKit,
  useDefaultRenderTool,
  useHumanInTheLoop,
} from "@copilotkit/react-core/v2";
import { CopilotKitCoreRuntimeConnectionStatus } from "@copilotkit/core";
import "@copilotkit/react-core/v2/styles.css";
import { DelegatePicker } from "./components/DelegatePicker";
import { ToolCallBlock } from "./components/ToolCallBlock";
import styles from "./page.module.css";

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
  const { agent } = useAgent({
    agentId: "ONEMPReadAgent",
    threadId,
  });
  const { copilotkit } = useCopilotKit();

  // Reason: guard against double-submission; reset when thread resets.
  const [submitted, setSubmitted] = useState(false);
  useEffect(() => {
    setSubmitted(false);
  }, [threadId]);

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

  // Reason: agent_framework_ag_ui translates approval_mode="always_require"
  // tool calls into a synthetic "confirm_changes" TOOL_CALL_* event sequence.
  // The frontend must intercept this synthetic tool — not the original Python
  // tool names — to avoid duplicate tool name errors on the backend.
  // Args shape: { function_name, function_call_id, function_arguments, steps }
  // Response shape: { accepted: bool, steps: [] } — required by
  // _is_confirm_changes_response in agent_framework_ag_ui._agent_run.
  useHumanInTheLoop({
    name: "confirm_changes",
    description: "Approval dialog for write operations requiring HITL confirmation",
    render: (props) => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const anyArgs = props.args as any;
      const toolName: string = anyArgs?.function_name ?? "unknown tool";
      const toolArgs: Record<string, unknown> = anyArgs?.function_arguments ?? {};

      if (props.status === "inProgress") {
        return (
          <div className={styles.approvalCard}>
            <div className={styles.approvalHeading}>Approval required — {toolName}</div>
            <p className={styles.approvalStatus}>Preparing…</p>
            <div className={styles.approvalActions}>
              <button type="button" aria-label={`Approve ${toolName}`} className={styles.approveBtn} disabled>Approve</button>
              <button type="button" aria-label={`Deny ${toolName}`} className={styles.denyBtn} disabled>Deny</button>
            </div>
          </div>
        );
      }

      if (props.status === "executing") {
        return (
          <div className={styles.approvalCard}>
            <div className={styles.approvalHeading}>Approval required — {toolName}</div>
            <dl className={styles.approvalArgs}>
              {Object.entries(toolArgs).map(([k, v]) => (
                <div key={k} className={styles.approvalArgRow}>
                  <dt className={styles.approvalArgKey}>{k}</dt>
                  <dd className={styles.approvalArgVal}>
                    {typeof v === "object" ? JSON.stringify(v) : String(v)}
                  </dd>
                </div>
              ))}
            </dl>
            <div className={styles.approvalActions}>
              <button
                type="button"
                aria-label={`Approve ${toolName}`}
                className={styles.approveBtn}
                disabled={submitted}
                onClick={() => {
                  setSubmitted(true);
                  props.respond({ accepted: true, steps: [] });
                }}
              >
                Approve
              </button>
              <button
                type="button"
                aria-label={`Deny ${toolName}`}
                className={styles.denyBtn}
                disabled={submitted}
                onClick={() => {
                  setSubmitted(true);
                  props.respond({ accepted: false, steps: [] });
                }}
              >
                Deny
              </button>
            </div>
          </div>
        );
      }

      // status === "complete"
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const wasAccepted = (props.result as any)?.accepted === true;
      return (
        <div className={styles.approvalCard}>
          <div className={styles.approvalHeading}>
            {toolName} — {wasAccepted ? "approved" : "denied"}
          </div>
        </div>
      );
    },
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
    <div className={styles.appShell}>
      <header className={styles.header}>
        <div className={styles.brand}>
          <span className={styles.brandMark}>OECD</span>
          <span className={styles.brandTitle}>ONE-MP Read Agent</span>
        </div>
        <div className={styles.personaBar}>
          <label className={styles.personaLabel} htmlFor="delegate-select">
            Acting as
          </label>
          <DelegatePicker
            onDelegateChange={handleDelegateChange}
            onThreadReset={handleThreadReset}
          />
        </div>
      </header>
      <main className={styles.main}>
        <div className={styles.container}>
          {selectedDelegateId !== "" && (
            <ChatPane threadId={threadId} delegateId={selectedDelegateId} />
          )}
        </div>
      </main>
    </div>
  );
}
