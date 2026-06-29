import {
  Database,
  FileSearch,
  Home,
  Wrench,
  CheckSquare,
  Brain,
} from "lucide-react";
import { cn } from "@/lib/utils";

const items = [
  { id: "dashboard", label: "Dashboard", icon: Home },
  { id: "datasets", label: "Datasets", icon: Database },
  { id: "mcp", label: "MCP Tools", icon: Wrench },
  { id: "skills", label: "Skills", icon: FileSearch },
  { id: "validation", label: "Validation", icon: CheckSquare },
];

interface SidebarProps {
  active: string;
  onNavigate: (id: string) => void;
}

export default function Sidebar({ active, onNavigate }: SidebarProps) {
  return (
    <aside className="w-60 h-screen flex flex-col border-r border-border bg-muted/30 shrink-0">
      <div className="flex items-center gap-2 px-5 py-5 border-b border-border">
        <Brain className="h-6 w-6 text-accent" />
        <span className="text-lg font-bold tracking-tight">NLI Studio</span>
      </div>
      <nav className="flex-1 py-4 px-3 space-y-1 overflow-auto">
        {items.map((item) => {
          const Icon = item.icon;
          const isActive = active === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                isActive
                  ? "bg-accent/10 text-accent"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </button>
          );
        })}
      </nav>
    </aside>
  );
}
