import { useEffect, useState } from "react";
import { getMcpStatus, listDatasets, listSkills, type McpStatusResponse, type DatasetListResponse } from "@/lib/api";
import { Card, CardHeader, CardTitle, CardValue } from "@/components/ui/card";
import { Wrench, Database, FileOutput, FileSearch } from "lucide-react";

export default function Dashboard() {
  const [mcp, setMcp] = useState<McpStatusResponse | null>(null);
  const [datasets, setDatasets] = useState<DatasetListResponse | null>(null);
  const [skills, setSkills] = useState<string[]>([]);

  useEffect(() => {
    getMcpStatus().then(setMcp).catch(() => {});
    listDatasets().then(setDatasets).catch(() => {});
    listSkills().then(setSkills).catch(() => {});
  }, []);

  return (
    <div className="p-8 space-y-8">
      <div>
        <h2 className="text-2xl font-bold">Dashboard</h2>
        <p className="text-sm text-muted-foreground mt-1">System overview and connection status</p>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardHeader>
            <Wrench className="h-5 w-5 text-accent mb-2" />
            <CardTitle>MCP Tools</CardTitle>
          </CardHeader>
          <CardValue>{mcp?.tool_count ?? "—"}</CardValue>
        </Card>
        <Card>
          <CardHeader>
            <Database className="h-5 w-5 text-accent mb-2" />
            <CardTitle>Input Datasets</CardTitle>
          </CardHeader>
          <CardValue>{datasets?.inputs.length ?? "—"}</CardValue>
        </Card>
        <Card>
          <CardHeader>
            <FileOutput className="h-5 w-5 text-accent mb-2" />
            <CardTitle>Output Datasets</CardTitle>
          </CardHeader>
          <CardValue>{datasets?.outputs.length ?? "—"}</CardValue>
        </Card>
        <Card>
          <CardHeader>
            <FileSearch className="h-5 w-5 text-accent mb-2" />
            <CardTitle>Skills</CardTitle>
          </CardHeader>
          <CardValue>{skills.length}</CardValue>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Connection</CardTitle>
        </CardHeader>
        <div className="space-y-2 text-sm">
          <div className="flex justify-between py-2 border-b border-border">
            <span className="text-muted-foreground">Backend Health</span>
            <span className="text-green-400">OK</span>
          </div>
          <div className="flex justify-between py-2 border-b border-border">
            <span className="text-muted-foreground">MCP Server</span>
            <span>{mcp?.server_name ?? "—"}</span>
          </div>
          <div className="flex justify-between py-2 border-b border-border">
            <span className="text-muted-foreground">MCP Connected</span>
            <span className={mcp?.connected ? "text-green-400" : "text-red-400"}>
              {mcp?.connected ? "Yes" : "No"}
            </span>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-muted-foreground">Tool Count</span>
            <span>{mcp?.tool_count ?? "—"}</span>
          </div>
        </div>
      </Card>
    </div>
  );
}
