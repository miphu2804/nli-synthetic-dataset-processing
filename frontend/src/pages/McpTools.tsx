import { useEffect, useState, useMemo } from "react";
import { getMcpStatus, type McpToolInfo } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Search, Wrench } from "lucide-react";

export default function McpTools() {
  const [tools, setTools] = useState<McpToolInfo[]>([]);
  const [serverName, setServerName] = useState("");
  const [connected, setConnected] = useState(false);
  const [search, setSearch] = useState("");

  useEffect(() => {
    getMcpStatus()
      .then((d) => {
        setTools(d.tools);
        setServerName(d.server_name);
        setConnected(d.connected);
      })
      .catch(() => {});
  }, []);

  const filtered = useMemo(() => {
    if (!search.trim()) return tools;
    const q = search.toLowerCase();
    return tools.filter(
      (t) => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)
    );
  }, [tools, search]);

  return (
    <div className="p-8 space-y-6">
      <div>
        <h2 className="text-2xl font-bold">MCP Tools</h2>
        <p className="text-sm text-muted-foreground mt-1">
          Server: {serverName} · Status:{" "}
          <span className={connected ? "text-green-400" : "text-red-400"}>
            {connected ? "Connected" : "Disconnected"}
          </span>
        </p>
      </div>

      <div className="relative max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
        <input
          type="text"
          placeholder="Search tools..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full rounded-xl border border-border bg-muted/50 pl-9 pr-4 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-accent"
        />
      </div>

      <div className="space-y-2">
        {filtered.length === 0 ? (
          <p className="text-sm text-muted-foreground">No tools found</p>
        ) : (
          filtered.map((t) => (
            <Card key={t.name} className="flex items-start gap-4 py-4 px-5">
              <Wrench className="h-5 w-5 text-accent shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <h4 className="text-sm font-medium">{t.name}</h4>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {t.description || "No description"}
                </p>
              </div>
              <Badge variant="secondary">tool</Badge>
            </Card>
          ))
        )}
      </div>
    </div>
  );
}
