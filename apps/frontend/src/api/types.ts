/**
 * Mirror of dcode_shared.schemas (DESIGN.md §4 Interface Contracts).
 *
 * Kept in sync manually for now. M2 swaps this for auto-generated types
 * from the FastAPI OpenAPI document via `openapi-typescript`.
 */

export type UUID = string;

export type RepoStatus =
  | 'queued'
  | 'cloning'
  | 'parsing'
  | 'embedding'
  | 'graphing'
  | 'ready'
  | 'failed';

export type StageState = 'pending' | 'in_progress' | 'done' | 'failed';

// --- Indexing API (DESIGN.md §4.1) ---

export interface RepoCreateRequest {
  url: string;
}

export interface RepoCreateResponse {
  repo_id: UUID;
  status: RepoStatus;
}

export interface StagesStatus {
  cloning: StageState;
  parsing: StageState;
  embedding: StageState;
  graphing: StageState;
}

export interface RepoStatusResponse {
  repo_id: UUID;
  status: RepoStatus;
  progress: number;
  stages: StagesStatus;
  error: string | null;
}

// --- Query API (DESIGN.md §4.3) ---

export interface QueryRequest {
  repo_id: UUID;
  query: string;
}

export type SSEEventName =
  | 'thought'
  | 'tool_call'
  | 'tool_result'
  | 'citation'
  | 'partial_answer'
  | 'final_answer'
  | 'error';

export interface ThoughtPayload {
  step: number;
  content: string;
}
export interface ToolCallPayload {
  step: number;
  tool: string;
  args: Record<string, unknown>;
}
export interface ToolResultPayload {
  step: number;
  tool: string;
  result_summary: string;
}
export interface CitationPayload {
  symbol: string;
  file_path: string;
  line: number;
  verified: boolean;
}
export interface PartialAnswerPayload {
  delta: string;
}
export interface FinalAnswerPayload {
  answer: string;
  citations: CitationPayload[];
  groundedness: number;
}
export interface ErrorPayload {
  code: string;
  message: string;
}
