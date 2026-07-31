/**
 * Hand-maintained mirror of the canonical dcode_shared.schemas contracts.
 *
 * Kept in sync manually for now. Replacing it with types generated from the
 * FastAPI OpenAPI document via `openapi-typescript` remains outstanding.
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

// --- Public indexing API ---

export interface RepoCreateRequest {
  url: string;
}

export interface RepoCreateResponse {
  repo_id: UUID;
  status: RepoStatus;
  /**
   * An existing repo with the same URL was returned instead of cloning it
   * again — nothing was queued. Response is 200, not 202.
   */
  reused: boolean;
}

export interface StagesStatus {
  cloning: StageState;
  parsing: StageState;
  embedding: StageState;
  graphing: StageState;
}

export interface RepoStatusResponse {
  repo_id: UUID;
  url: string;
  status: RepoStatus;
  progress: number;
  stages: StagesStatus;
  error: string | null;
  warnings: string[];
}

// --- Public query API ---

export interface QueryTurn {
  role: 'user' | 'assistant';
  content: string;
}

export interface QueryRequest {
  repo_id: UUID;
  query: string;
  /** Prior turns for multi-turn follow-ups (bounded by the gateway). */
  history?: QueryTurn[];
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

export type QueryStreamEvent =
  | { event: 'thought'; data: ThoughtPayload }
  | { event: 'tool_call'; data: ToolCallPayload }
  | { event: 'tool_result'; data: ToolResultPayload }
  | { event: 'citation'; data: CitationPayload }
  | { event: 'partial_answer'; data: PartialAnswerPayload }
  | { event: 'final_answer'; data: FinalAnswerPayload }
  | { event: 'error'; data: ErrorPayload };

// --- Inspector API (read-only source + call graph — mirror of dcode_shared) ---

export interface Location {
  symbol: string;
  file_path: string;
  line: number;
  chunk_id: string | null;
}

export type SourceGranularity = 'chunk' | 'symbol_chunk' | 'file_outline' | 'none';

export interface SourceResponse {
  found: boolean;
  granularity: SourceGranularity;
  file_path: string | null;
  symbol_name: string | null;
  chunk_type: string | null;
  start_line: number | null;
  end_line: number | null;
  cited_line: number | null;
  content: string | null;
  outline: Location[];
  language: string;
}

export interface SymbolNeighbors {
  found: boolean;
  symbol: string | null;
  file_path: string | null;
  line: number | null;
  called_by: Location[];
  calls: Location[];
  references: Location[];
}
