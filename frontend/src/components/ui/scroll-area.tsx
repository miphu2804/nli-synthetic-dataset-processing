import { cn } from "@/lib/utils";
import type { HTMLAttributes } from "react";

function ScrollArea({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn("overflow-auto", className)}
      {...props}
    />
  );
}

export { ScrollArea };
