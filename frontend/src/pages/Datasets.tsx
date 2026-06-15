import { useEffect, useState, useCallback } from "react";
import { listDatasets, readDataset, type FileInfo, type DatasetReadResponse } from "@/lib/api";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Database, FileText } from "lucide-react";

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function FileList({
  files,
  title,
  onSelect,
}: {
  files: FileInfo[];
  title: string;
  onSelect: (f: FileInfo) => void;
}) {
  return (
    <div className="space-y-2">
      <h3 className="text-sm font-medium text-muted-foreground">{title}</h3>
      {files.length === 0 ? (
        <p className="text-sm text-muted-foreground italic">No files found</p>
      ) : (
        files.map((f) => (
          <button
            key={f.path}
            onClick={() => onSelect(f)}
            className="flex w-full items-center justify-between rounded-xl border border-border p-3 hover:bg-muted/50 transition-colors text-left"
          >
            <div className="flex items-center gap-3">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-medium">{f.name}</span>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="outline">{f.kind}</Badge>
              <span className="text-xs text-muted-foreground">{formatBytes(f.size_bytes)}</span>
            </div>
          </button>
        ))
      )}
    </div>
  );
}

export default function Datasets() {
  const [inputs, setInputs] = useState<FileInfo[]>([]);
  const [outputs, setOutputs] = useState<FileInfo[]>([]);
  const [selected, setSelected] = useState<FileInfo | null>(null);
  const [preview, setPreview] = useState<DatasetReadResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    listDatasets()
      .then((d) => { setInputs(d.inputs); setOutputs(d.outputs); })
      .catch(() => {});
  }, []);

  const handleSelect = useCallback(async (f: FileInfo) => {
    setSelected(f);
    setLoading(true);
    try {
      const data = await readDataset(f.path, 20, 0);
      setPreview(data);
    } catch {
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <div className="p-8 h-full flex flex-col overflow-hidden">
      <div className="mb-6 shrink-0">
        <h2 className="text-2xl font-bold">Datasets</h2>
        <p className="text-sm text-muted-foreground mt-1">Browse and inspect dataset files</p>
      </div>

      <div className="flex gap-6 flex-1 min-h-0">
        <div className="w-80 shrink-0 space-y-6 overflow-auto">
          <Tabs defaultValue="input">
            <TabsList className="w-full grid grid-cols-2">
              <TabsTrigger value="input">Input</TabsTrigger>
              <TabsTrigger value="output">Output</TabsTrigger>
            </TabsList>
            <TabsContent value="input">
              <FileList files={inputs} title="data/original/ & data/processed/" onSelect={handleSelect} />
            </TabsContent>
            <TabsContent value="output">
              <FileList files={outputs} title="data/generated/ & data/validated/" onSelect={handleSelect} />
            </TabsContent>
          </Tabs>
        </div>

        <div className="flex-1 min-w-0">
          {!selected ? (
            <Card className="h-full flex items-center justify-center">
              <div className="text-center text-muted-foreground">
                <Database className="h-12 w-12 mx-auto mb-3 opacity-30" />
                <p>Select a dataset to preview</p>
              </div>
            </Card>
          ) : loading ? (
            <Card className="h-full flex items-center justify-center">
              <p className="text-muted-foreground">Loading...</p>
            </Card>
          ) : preview ? (
            <Card className="h-full flex flex-col min-h-0">
              <CardHeader className="shrink-0">
                <div className="flex items-center gap-2 mb-1">
                  <CardTitle className="text-foreground text-base">{selected.name}</CardTitle>
                  <Badge variant="outline">{preview.format}</Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  {preview.row_count} rows · {preview.column_count} columns · {formatBytes(selected.size_bytes)}
                </p>
              </CardHeader>
              <ScrollArea className="flex-1 min-h-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      {preview.columns.map((col) => (
                        <TableHead key={col}>{col}</TableHead>
                      ))}
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {preview.rows.map((row, i) => (
                      <TableRow key={i}>
                        {preview.columns.map((col) => (
                          <TableCell key={col}>
                            <span className="text-xs">{String(row[col] ?? "")}</span>
                          </TableCell>
                        ))}
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </ScrollArea>
            </Card>
          ) : (
            <Card className="h-full flex items-center justify-center">
              <p className="text-muted-foreground">Failed to load dataset</p>
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
