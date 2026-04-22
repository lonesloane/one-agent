"use client";

import { useEffect, useRef, useState } from "react";
import styles from "./DelegatePicker.module.css";

interface Delegate {
  id: string;
  full_name: string;
  delegation_name: string;
  role: string;
}

interface DelegatePickerProps {
  onDelegateChange: (delegateId: string) => void;
  onThreadReset: () => void;
}

const AGENT_BASE =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8000";
const DELEGATES_URL = `${AGENT_BASE}/api/delegates`;

export function DelegatePicker({
  onDelegateChange,
  onThreadReset,
}: DelegatePickerProps) {
  const [delegates, setDelegates] = useState<Delegate[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [error, setError] = useState<boolean>(false);
  const fetchedRef = useRef(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;

    fetch(DELEGATES_URL)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json() as Promise<Delegate[]>;
      })
      .then((data) => {
        setDelegates(data);
        if (data.length > 0) {
          const first = data[0];
          setSelectedId(first.id);
          onDelegateChange(first.id);
        }
      })
      .catch(() => {
        setError(true);
      });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  function handleChange(e: React.ChangeEvent<HTMLSelectElement>) {
    const newId = e.target.value;
    setSelectedId(newId);
    onDelegateChange(newId);
    onThreadReset();
  }

  if (error) {
    return (
      <select id="delegate-select" disabled className={styles.select}>
        <option>Failed to load delegates</option>
      </select>
    );
  }

  if (delegates.length === 0) {
    return (
      <select id="delegate-select" disabled className={styles.select}>
        <option>No delegates available</option>
      </select>
    );
  }

  return (
    <select
      id="delegate-select"
      value={selectedId}
      onChange={handleChange}
      className={styles.select}
    >
      {delegates.map((d) => (
        <option key={d.id} value={d.id}>
          {d.full_name} ({d.delegation_name} — {d.role})
        </option>
      ))}
    </select>
  );
}
