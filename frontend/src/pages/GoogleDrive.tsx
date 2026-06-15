import { useEffect, useState, useCallback } from "react";
import {
  driveAuthStatus,
  driveAuthStart,
  driveAuthComplete,
  browseDriveFiles,
  driveDownload,
  driveUpload,
  type BrowseDriveFilesResponse,
  type DriveAuthStartResponse,
} from "@/lib/api";
import { Card, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AlertTriangle, Download, Upload, HardDrive } from "lucide-react";

export default function GoogleDrive() {
  const [authenticated, setAuthenticated] = useState(false);
  const [authStep, setAuthStep] = useState<"idle" | "pending" | "done">("idle");
  const [authData, setAuthData] = useState<DriveAuthStartResponse | null>(null);
  const [browse, setBrowse] = useState<BrowseDriveFilesResponse | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    driveAuthStatus().then((s) => {
      setAuthenticated(s.authenticated);
      if (s.authenticated) setAuthStep("done");
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (authenticated) {
      browseDriveFiles().then(setBrowse).catch(() => {});
    }
  }, [authenticated]);

  const handleStartAuth = async () => {
    try {
      const data = await driveAuthStart();
      setAuthData(data);
      setAuthStep("pending");
    } catch {}
  };

  const handleCheckAuth = async () => {
    try {
      setPolling(true);
      const result = await driveAuthComplete();
      if (result.authenticated) {
        setAuthenticated(true);
        setAuthStep("done");
      }
    } catch {} finally {
      setPolling(false);
    }
  };

  const handleDownload = useCallback(async (fileId: string) => {
    try {
      const result = await driveDownload(fileId);
      alert(`Download stub: ${result.drive_file_id} → ${result.local_path}`);
    } catch {}
  }, []);

  const handleUpload = useCallback(async () => {
    try {
      const result = await driveUpload("data/sample.csv");
      alert(`Upload stub: ${result.drive_file_id} → ${result.web_view_link}`);
    } catch {}
  }, []);

  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold">Google Drive</h2>
          <p className="text-sm text-muted-foreground mt-1">Browse and sync datasets</p>
        </div>
        <Badge variant="outline" className="flex items-center gap-1.5 border-yellow-600 text-yellow-400">
          <AlertTriangle className="h-3 w-3" /> STUB MODE
        </Badge>
      </div>

      {!authenticated ? (
        <Card className="max-w-md">
          <CardHeader>
            <CardTitle>Connect Google Drive</CardTitle>
          </CardHeader>
          <div className="space-y-4">
            {authStep === "idle" && (
              <Button onClick={handleStartAuth} className="w-full">
                Login with Google
              </Button>
            )}
            {authStep === "pending" && authData && (
              <>
                <div className="rounded-xl border border-border p-4 space-y-2 bg-muted/30">
                  <p className="text-sm text-muted-foreground">Go to this URL and enter the code:</p>
                  <p className="text-sm font-mono break-all">{authData.verification_url}</p>
                  <p className="text-2xl font-bold tracking-widest text-accent">{authData.user_code}</p>
                  <p className="text-xs text-muted-foreground">Expires in {authData.expires_in}s</p>
                </div>
                <Button onClick={handleCheckAuth} disabled={polling} className="w-full" variant="outline">
                  {polling ? "Checking..." : "I've entered the code"}
                </Button>
              </>
            )}
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          <div className="flex items-center gap-4">
            <Button onClick={() => browseDriveFiles().then(setBrowse).catch(() => {})} variant="outline" size="sm">
              Refresh
            </Button>
            <Button onClick={handleUpload} size="sm" className="flex items-center gap-2">
              <Upload className="h-4 w-4" /> Upload
            </Button>
          </div>

          {browse && (
            <>
              <div className="flex items-center gap-4">
                <h4 className="text-sm font-medium text-muted-foreground">Subfolders</h4>
                {browse.subfolders.map((f) => (
                  <Badge key={f.file_id} variant="secondary" className="cursor-pointer hover:bg-muted">
                    <HardDrive className="h-3 w-3 mr-1" />
                    {f.name}
                  </Badge>
                ))}
              </div>

              <Card>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Name</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Size</TableHead>
                      <TableHead className="w-24">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {browse.files.map((f) => (
                      <TableRow key={f.file_id}>
                        <TableCell className="font-medium text-sm">{f.name}</TableCell>
                        <TableCell><Badge variant="outline">{f.mime_type}</Badge></TableCell>
                        <TableCell className="text-sm text-muted-foreground">
                          {f.size_bytes ? `${(f.size_bytes / 1024).toFixed(0)} KB` : "—"}
                        </TableCell>
                        <TableCell>
                          <Button size="sm" variant="ghost" onClick={() => handleDownload(f.file_id)}>
                            <Download className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </Card>
            </>
          )}
        </div>
      )}
    </div>
  );
}
