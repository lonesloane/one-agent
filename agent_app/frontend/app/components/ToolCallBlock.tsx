import styles from "./ToolCallBlock.module.css";

type ToolCallStatus = "inProgress" | "executing" | "complete";

interface ToolCallBlockProps {
  name: string;
  status: ToolCallStatus;
  parameters: unknown;
  result: string | undefined;
}

const STATUS_CLASS: Record<ToolCallStatus, string> = {
  complete: styles.statusComplete,
  executing: styles.statusExecuting,
  inProgress: styles.statusInProgress,
};

export function ToolCallBlock({
  name,
  status,
  parameters,
  result,
}: ToolCallBlockProps) {
  return (
    <details className={styles.block}>
      <summary className={styles.summary}>
        <svg
          className={styles.chevron}
          viewBox="0 0 10 10"
          aria-hidden="true"
          focusable="false"
        >
          <path
            d="M3 2 L7 5 L3 8"
            stroke="currentColor"
            fill="none"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
        <span className={styles.name}>{name}</span>
        <span className={`${styles.statusPill} ${STATUS_CLASS[status]}`}>
          {status}
        </span>
      </summary>
      <div className={styles.body}>
        <pre className={styles.paramsBlock}>
          {JSON.stringify(parameters, null, 2)}
        </pre>
        {status === "complete" && result !== undefined && (
          <>
            <div className={styles.resultLabel}>Result</div>
            <pre className={styles.resultBlock}>{result}</pre>
          </>
        )}
      </div>
    </details>
  );
}
