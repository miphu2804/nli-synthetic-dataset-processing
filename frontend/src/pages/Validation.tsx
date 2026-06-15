import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { CheckSquare, Users, BarChart3, ShieldCheck } from "lucide-react";

export default function Validation() {
  return (
    <div className="p-8 relative h-full">
      <div className="mb-6">
        <h2 className="text-2xl font-bold">Validation</h2>
        <p className="text-sm text-muted-foreground mt-1">Pipeline validation and quality assurance</p>
      </div>

      <div className="grid grid-cols-4 gap-4 mb-8">
        <Card className="text-center py-8">
          <CheckSquare className="h-8 w-8 text-accent mx-auto mb-3" />
          <p className="text-sm font-medium">Masked Validation</p>
          <p className="text-xs text-muted-foreground mt-1">Labels hidden from validators</p>
        </Card>
        <Card className="text-center py-8">
          <Users className="h-8 w-8 text-accent mx-auto mb-3" />
          <p className="text-sm font-medium">Independent Validators</p>
          <p className="text-xs text-muted-foreground mt-1">Multiple LLM judges</p>
        </Card>
        <Card className="text-center py-8">
          <BarChart3 className="h-8 w-8 text-accent mx-auto mb-3" />
          <p className="text-sm font-medium">Vote Consensus</p>
          <p className="text-xs text-muted-foreground mt-1">PMI & majority voting</p>
        </Card>
        <Card className="text-center py-8">
          <ShieldCheck className="h-8 w-8 text-accent mx-auto mb-3" />
          <p className="text-sm font-medium">Trusted Decision</p>
          <p className="text-xs text-muted-foreground mt-1">Final label assignment</p>
        </Card>
      </div>

      <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
        <div className="bg-background/80 backdrop-blur-sm rounded-2xl border border-border px-12 py-8 text-center">
          <Badge variant="secondary" className="text-lg px-6 py-2 mb-4">
            Coming Soon
          </Badge>
          <p className="text-muted-foreground text-sm max-w-md">
            The validation pipeline is under development. Check back for masked validation,
            vote consensus, and trusted decision workflows.
          </p>
        </div>
      </div>
    </div>
  );
}
