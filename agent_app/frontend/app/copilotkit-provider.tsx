"use client";

import { CopilotKitProvider as V2Provider } from "@copilotkit/react-core/v2";
import "@copilotkit/react-core/v2/styles.css";
import { ReactNode } from "react";

interface CopilotKitProviderProps {
  children: ReactNode;
}

export function CopilotKitProvider({
  children,
}: CopilotKitProviderProps) {
  return (
    <V2Provider runtimeUrl="/api/copilotkit">
      {children}
    </V2Provider>
  );
}
