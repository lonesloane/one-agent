import {
  CopilotRuntime,
  createCopilotRuntimeHandler,
} from "@copilotkit/runtime/v2";
import { HttpAgent } from "@ag-ui/client";

const agentUrl = process.env.AGENT_URL ?? "http://localhost:8000/";

const runtime = new CopilotRuntime({
  agents: {
    ONEMPReadAgent: new HttpAgent({ url: agentUrl }),
  },
});

const handler = createCopilotRuntimeHandler({
  runtime,
  basePath: "/api/copilotkit",
});

export { handler as GET, handler as POST };
