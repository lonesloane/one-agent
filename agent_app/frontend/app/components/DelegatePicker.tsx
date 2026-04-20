"use client";

import { useEffect, useRef, useState } from "react";
import { useCoAgent } from "@copilotkit/react-core";

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

const DELEGATES_URL = "http://localhost:8000/api/delegates";

export function DelegatePicker({
  onDelegateChange,
  onThreadReset,
}: DelegatePickerProps) {
  const [delegates, setDelegates] = useState<Delegate[]>([]);
  const [selectedId, setSelectedId] = useState<string>("");
  const [error, setError] = useState<boolean>(false);
  const fetchedRef = useRef(false);

  const { setState } = useCoAgent<{ delegate_id: string }>({
    name: "ONEMPReadAgent",
    initialState: { delegate_id: "" },
  });

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
          setState({ delegate_id: first.id });
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
    setState({ delegate_id: newId });
    onDelegateChange(newId);
    onThreadReset();
  }

  if (error) {
    return (
      <select disabled style={{ opacity: 0.5 }}>
        <option>Failed to load delegates</option>
      </select>
    );
  }

  if (delegates.length === 0) {
    return (
      <select disabled style={{ opacity: 0.5 }}>
        <option>No delegates available</option>
      </select>
    );
  }

  return (
    <select value={selectedId} onChange={handleChange}>
      {delegates.map((d) => (
        <option key={d.id} value={d.id}>
          {d.full_name} ({d.delegation_name} — {d.role})
        </option>
      ))}
    </select>
  );
}
