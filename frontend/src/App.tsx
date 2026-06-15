import { useState } from "react";
import Sidebar from "@/components/Sidebar";
import StatusBar from "@/components/StatusBar";
import Dashboard from "@/pages/Dashboard";
import Datasets from "@/pages/Datasets";
import McpTools from "@/pages/McpTools";
import Skills from "@/pages/Skills";
import GoogleDrive from "@/pages/GoogleDrive";
import Validation from "@/pages/Validation";

export default function App() {
  const [page, setPage] = useState("dashboard");

  return (
    <div className="flex h-screen w-screen overflow-hidden">
      <Sidebar active={page} onNavigate={setPage} />
      <div className="flex flex-1 flex-col min-w-0">
        <StatusBar />
        <main className="flex-1 overflow-auto">
          {page === "dashboard" && <Dashboard />}
          {page === "datasets" && <Datasets />}
          {page === "mcp" && <McpTools />}
          {page === "skills" && <Skills />}
          {page === "drive" && <GoogleDrive />}
          {page === "validation" && <Validation />}
        </main>
      </div>
    </div>
  );
}
