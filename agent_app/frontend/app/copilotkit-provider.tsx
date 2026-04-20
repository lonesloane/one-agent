"use client";

import { CopilotKit } from "@copilotkit/react-core";
import "@copilotkit/react-ui/styles.css";
import { ReactNode } from "react";

interface CopilotKitProviderProps {
  children: ReactNode;
}

export function CopilotKitProvider({
  children,
}: CopilotKitProviderProps) {
  return (
    <CopilotKit runtimeUrl="/api/copilotkit" agent="ONEMPReadAgent">
      {children}
    </CopilotKit>
  );
}
