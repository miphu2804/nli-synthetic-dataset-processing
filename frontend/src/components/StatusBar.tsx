import { useEffect, useState } from "react";
import { getHealth, getMcpStatus, type McpStatusResponse } from "@/lib/api";

interface StatusBarProps {
  onData?: (data: McpStatusResponse) => void;
}

export default function StatusBar({ onData }: StatusBarProps) {
  const [backendOk, setBackendOk] = useState(false);
  const [mcpConnected, setMcpConnected] = useState(false);

  useEffect(() => {
    let active = true;
    async function poll() {
      try {
        const health = await getHealth();
        if (!active) return;
        setBackendOk(health.status === "ok");

        const mcp = await getMcpStatus();
        if (!active) return;
        setMcpConnected(mcp.connected);
        onData?.(mcp);
      } catch {
        if (active) {
          setBackendOk(false);
          setMcpConnected(false);
        }
      }
    }
    poll();
    const timer = setInterval(poll, 10_000);
    return () => { active = false; clearInterval(timer); };
  }, [onData]);

  return (
    <div className="flex items-center justify-between px-6 py-2 border-b border-border bg-muted/20 shrink-0">
      <div className="flex items-center gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span
            className={`h-2 w-2 rounded-full ${
              backendOk ? "bg-green-400 shadow-[0_0_6px_rgba(45,212,191,0.5)]" : "bg-red-400"
            }`}
          />
          {backendOk ? "Connected" : "Disconnected"}
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className={`h-2 w-2 rounded-full ${
              mcpConnected ? "bg-green-400 shadow-[0_0_6px_rgba(45,212,191,0.5)]" : "bg-red-400"
            }`}
          />
          MCP {mcpConnected ? "Online" : "Offline"}
        </span>
      </div>
    </div>
  );
}
