import type {
  AdaptersResult,
  AnalyzeResult,
  ApiError,
  AuthorResult,
  BatchItemResult,
  CompileResult,
  CritiqueResult,
  Example,
  ExportResult,
  FoldResult,
  Format,
  ResolveResult,
  ResolvedDesign,
  RunSummary,
  StructureInfo,
} from "./types";

async function postJson<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw await readError(res);
  return res.json();
}

async function readError(res: Response): Promise<ApiError> {
  try {
    const body = await res.json();
    const d = body.detail;
    if (d && typeof d === "object") return d as ApiError;
    return { type: "error", message: typeof d === "string" ? d : res.statusText };
  } catch {
    return { type: "error", message: `${res.status} ${res.statusText}` };
  }
}

export async function getExamples(): Promise<Example[]> {
  const res = await fetch("/api/examples");
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function compile(source: string, format: Format): Promise<CompileResult> {
  const res = await fetch("/api/compile", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, format }),
  });
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function compileBatch(
  items: { source: string; format: Format }[]
): Promise<BatchItemResult[]> {
  const res = await fetch("/api/compile-batch", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ items }),
  });
  if (!res.ok) throw await readError(res);
  return (await res.json()).results;
}

export async function compileLibrary(
  source: string,
  format: Format,
  genes: string[]
): Promise<BatchItemResult[]> {
  const res = await fetch("/api/compile-library", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, format, genes }),
  });
  if (!res.ok) throw await readError(res);
  return (await res.json()).results;
}

// --- server-side run history ---

export async function getRuns(): Promise<RunSummary[]> {
  const res = await fetch("/api/runs");
  if (!res.ok) throw await readError(res);
  return (await res.json()).runs;
}

export async function getRun(id: string): Promise<CompileResult> {
  const res = await fetch(`/api/runs/${id}`);
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function saveRun(result: CompileResult): Promise<RunSummary> {
  const res = await fetch("/api/runs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ design: result.design, protocol: result.protocol }),
  });
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function clearRuns(): Promise<void> {
  await fetch("/api/runs", { method: "DELETE" });
}

// --- LLM agents (opt-in; require ANTHROPIC_API_KEY on the backend) ---

export async function getAiConfigured(): Promise<{ configured: boolean; demo: boolean }> {
  try {
    const j = await (await fetch("/api/health")).json();
    return { configured: !!j.ai_configured, demo: !!j.ai_demo };
  } catch {
    return { configured: false, demo: false };
  }
}

export async function author(request: string, model?: string): Promise<AuthorResult> {
  const res = await fetch("/api/author", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request, model }),
  });
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function resolveGene(gene: string, build: string, provider: string): Promise<ResolveResult> {
  return postJson<ResolveResult>("/api/resolve", { gene, build, provider });
}

export async function getAdapters(): Promise<AdaptersResult> {
  const res = await fetch("/api/adapters");
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function foldDomain(region: string): Promise<FoldResult> {
  return postJson<FoldResult>("/api/fold", { region });
}

export async function exportOligos(design: ResolvedDesign): Promise<ExportResult> {
  return postJson<ExportResult>("/api/export", { design });
}

export async function exampleReads(design: ResolvedDesign): Promise<{ reads: string; count: number }> {
  return postJson("/api/example-reads", { design });
}

export async function analyzeReads(design: ResolvedDesign, reads: string): Promise<AnalyzeResult> {
  return postJson<AnalyzeResult>("/api/analyze", { design, reads });
}

export async function getStructure(design: ResolvedDesign): Promise<StructureInfo> {
  const res = await fetch("/api/structure", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ design }),
  });
  if (!res.ok) throw await readError(res);
  return res.json();
}

export async function critique(source: string, format: Format, model?: string): Promise<CritiqueResult> {
  const res = await fetch("/api/critique", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ source, format, model }),
  });
  if (!res.ok) throw await readError(res);
  return res.json();
}
