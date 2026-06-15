import { useEffect, useState, useCallback } from "react";
import { listSkills, getSkill } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { FileSearch } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function Skills() {
  const [skills, setSkills] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listSkills().then(setSkills).catch(() => {});
  }, []);

  const handleSelect = useCallback(async (name: string) => {
    setSelected(name);
    setLoading(true);
    try {
      const data = await getSkill(name);
      setContent(data.content);
    } catch {
      setContent(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="p-8 h-full flex flex-col overflow-hidden">
      <div className="mb-6 shrink-0">
        <h2 className="text-2xl font-bold">Skills</h2>
        <p className="text-sm text-muted-foreground mt-1">NLI pipeline skills and resources</p>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        <div className="w-60 shrink-0 space-y-1 overflow-auto">
          {skills.length === 0 ? (
            <p className="text-sm text-muted-foreground">No skills available</p>
          ) : (
            skills.map((s) => (
              <button
                key={s}
                onClick={() => handleSelect(s)}
                className={`flex w-full items-center gap-2 rounded-xl px-3 py-2 text-sm transition-colors text-left ${
                  selected === s
                    ? "bg-accent/10 text-accent font-medium"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                }`}
              >
                <FileSearch className="h-4 w-4 shrink-0" />
                {s}
              </button>
            ))
          )}
        </div>

        <div className="flex-1 min-w-0">
          {!selected ? (
            <Card className="h-full flex items-center justify-center">
              <p className="text-muted-foreground">Select a skill to view</p>
            </Card>
          ) : loading ? (
            <Card className="h-full flex items-center justify-center">
              <p className="text-muted-foreground">Loading...</p>
            </Card>
          ) : content ? (
            <Card className="h-full p-8">
              <ScrollArea className="h-full">
                <div className="prose prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
                </div>
              </ScrollArea>
            </Card>
          ) : (
            <Card className="h-full flex items-center justify-center">
              <p className="text-muted-foreground">Failed to load skill</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
