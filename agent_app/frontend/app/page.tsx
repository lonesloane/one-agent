"use client";

import { useEffect, useState } from "react";
import {
  CopilotChat,
  useAgent,
  useCopilotKit,
  useDefaultRenderTool,
} from "@copilotkit/react-core/v2";
import { useHumanInTheLoop } from "@copilotkit/react-core";
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
  const [delegateSubmitted, setDelegateSubmitted] = useState(false);
  const [darSubmitted, setDarSubmitted] = useState(false);
  useEffect(() => {
    setDelegateSubmitted(false);
    setDarSubmitted(false);
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

  useHumanInTheLoop({
    name: "create_delegate",
    description: "Create a new delegate in a delegation",
    parameters: [
      { name: "full_name", type: "string", description: "Full name of the new delegate" },
      { name: "email", type: "string", description: "Email address of the new delegate" },
      { name: "function", type: "string", description: "Function or job title of the new delegate" },
      { name: "delegation_id", type: "string", description: "Delegation ID the delegate belongs to (e.g. 'FRA')" },
      { name: "role", type: "string", description: "Role for the new delegate: 'DELEGATE' or 'DELEGATION_EDITOR'. Defaults to 'DELEGATE'." },
    ],
    render: (props) => {
      if (props.status === "inProgress") {
        return (
          <div className={styles.approvalCard}>
            <div className={styles.approvalHeading}>Approval required — create_delegate</div>
            <p className={styles.approvalStatus}>Preparing…</p>
            {Object.keys(props.args).length > 0 && (
              <dl className={styles.approvalArgs}>
                {Object.entries(props.args).map(([k, v]) => (
                  <div key={k} className={styles.approvalArgRow}>
                    <dt className={styles.approvalArgKey}>{k}</dt>
                    <dd className={styles.approvalArgVal}>{String(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
            <div className={styles.approvalActions}>
              <button type="button" aria-label="Approve create_delegate" className={styles.approveBtn} disabled>Approve</button>
              <button type="button" aria-label="Deny create_delegate" className={styles.denyBtn} disabled>Deny</button>
            </div>
          </div>
        );
      }

      if (props.status === "executing") {
        return (
          <div className={styles.approvalCard}>
            <div className={styles.approvalHeading}>Approval required — create_delegate</div>
            <dl className={styles.approvalArgs}>
              {Object.entries(props.args).map(([k, v]) => (
                <div key={k} className={styles.approvalArgRow}>
                  <dt className={styles.approvalArgKey}>{k}</dt>
                  <dd className={styles.approvalArgVal}>{String(v)}</dd>
                </div>
              ))}
            </dl>
            <div className={styles.approvalActions}>
              <button
                type="button"
                aria-label="Approve create_delegate"
                className={styles.approveBtn}
                disabled={delegateSubmitted}
                onClick={() => { setDelegateSubmitted(true); props.respond({ approved: true }); }}
              >
                Approve
              </button>
              <button
                type="button"
                aria-label="Deny create_delegate"
                className={styles.denyBtn}
                disabled={delegateSubmitted}
                onClick={() => { setDelegateSubmitted(true); props.respond({ approved: false }); }}
              >
                Deny
              </button>
            </div>
          </div>
        );
      }

      // status === "complete"
      const wasApproved = props.result?.approved === true || props.result === true;
      return (
        <div className={styles.approvalCard}>
          <div className={styles.approvalHeading}>
            create_delegate — {wasApproved ? "approved" : "denied"}
          </div>
          {props.result !== undefined && (
            <pre className={styles.approvalResult}>{JSON.stringify(props.result, null, 2)}</pre>
          )}
        </div>
      );
    },
  });

  useHumanInTheLoop({
    name: "create_document_access_rights",
    description: "Create a document access right for a delegate",
    parameters: [
      { name: "delegate_id", type: "string", description: "Target delegate ID (DEL-YYYY-NNNN)" },
      { name: "committee_id", type: "string", description: "Committee ID, e.g. 'EDU'" },
      { name: "retroactive", type: "boolean", description: "Whether access applies to past documents" },
    ],
    render: (props) => {
      if (props.status === "inProgress") {
        return (
          <div className={styles.approvalCard}>
            <div className={styles.approvalHeading}>Approval required — create_document_access_rights</div>
            <p className={styles.approvalStatus}>Preparing…</p>
            {Object.keys(props.args).length > 0 && (
              <dl className={styles.approvalArgs}>
                {Object.entries(props.args).map(([k, v]) => (
                  <div key={k} className={styles.approvalArgRow}>
                    <dt className={styles.approvalArgKey}>{k}</dt>
                    <dd className={styles.approvalArgVal}>{String(v)}</dd>
                  </div>
                ))}
              </dl>
            )}
            <div className={styles.approvalActions}>
              <button type="button" aria-label="Approve create_document_access_rights" className={styles.approveBtn} disabled>Approve</button>
              <button type="button" aria-label="Deny create_document_access_rights" className={styles.denyBtn} disabled>Deny</button>
            </div>
          </div>
        );
      }

      if (props.status === "executing") {
        return (
          <div className={styles.approvalCard}>
            <div className={styles.approvalHeading}>Approval required — create_document_access_rights</div>
            <dl className={styles.approvalArgs}>
              {Object.entries(props.args).map(([k, v]) => (
                <div key={k} className={styles.approvalArgRow}>
                  <dt className={styles.approvalArgKey}>{k}</dt>
                  <dd className={styles.approvalArgVal}>{String(v)}</dd>
                </div>
              ))}
            </dl>
            <div className={styles.approvalActions}>
              <button
                type="button"
                aria-label="Approve create_document_access_rights"
                className={styles.approveBtn}
                disabled={darSubmitted}
                onClick={() => { setDarSubmitted(true); props.respond({ approved: true }); }}
              >
                Approve
              </button>
              <button
                type="button"
                aria-label="Deny create_document_access_rights"
                className={styles.denyBtn}
                disabled={darSubmitted}
                onClick={() => { setDarSubmitted(true); props.respond({ approved: false }); }}
              >
                Deny
              </button>
            </div>
          </div>
        );
      }

      // status === "complete"
      const wasApproved = props.result?.approved === true || props.result === true;
      return (
        <div className={styles.approvalCard}>
          <div className={styles.approvalHeading}>
            create_document_access_rights — {wasApproved ? "approved" : "denied"}
          </div>
          {props.result !== undefined && (
            <pre className={styles.approvalResult}>{JSON.stringify(props.result, null, 2)}</pre>
          )}
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
