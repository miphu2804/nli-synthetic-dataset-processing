import { cn } from "@/lib/utils";
import { createContext, useContext, useState, type ReactNode } from "react";

interface TabsContextType {
  value: string;
  onValueChange: (v: string) => void;
}

const TabsContext = createContext<TabsContextType>({ value: "", onValueChange: () => {} });

function Tabs({
  defaultValue,
  value,
  onValueChange,
  children,
}: {
  defaultValue?: string;
  value?: string;
  onValueChange?: (v: string) => void;
  children: ReactNode;
}) {
  const [internal, setInternal] = useState(defaultValue || "");
  const ctx = {
    value: value ?? internal,
    onValueChange: onValueChange ?? setInternal,
  };
  return <TabsContext.Provider value={ctx}>{children}</TabsContext.Provider>;
}

function TabsList({
  className,
  children,
}: {
  className?: string;
  children: ReactNode;
}) {
  return (
    <div className={cn("inline-flex gap-1 rounded-xl bg-muted p-1", className)}>
      {children}
    </div>
  );
}

function TabsTrigger({
  value,
  className,
  children,
}: {
  value: string;
  className?: string;
  children: ReactNode;
}) {
  const ctx = useContext(TabsContext);
  const active = ctx.value === value;
  return (
    <button
      className={cn(
        "px-4 py-2 text-sm font-medium rounded-lg transition-colors",
        active ? "bg-background text-foreground shadow-sm" : "text-muted-foreground hover:text-foreground",
        className
      )}
      onClick={() => ctx.onValueChange(value)}
    >
      {children}
    </button>
  );
}

function TabsContent({
  value,
  className,
  children,
}: {
  value: string;
  className?: string;
  children: ReactNode;
}) {
  const ctx = useContext(TabsContext);
  if (ctx.value !== value) return null;
  return <div className={cn("mt-4", className)}>{children}</div>;
}

export { Tabs, TabsContent, TabsList, TabsTrigger };
