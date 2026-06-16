/**
 * Typed API client — single point of contact with the gateway.
 * The SPA never calls the agent or DB directly; everything flows
 * through /api/v1/* on the gateway.
 */

import type {
  ErrorPayload,
  FinalAnswerPayload,
  PartialAnswerPayload,
  QueryRequest,
  QueryStreamEvent,
  RepoCreateRequest,
  RepoCreateResponse,
  RepoStatusResponse,
  SSEEventName,
  ThoughtPayload,
  ToolCallPayload,
  ToolResultPayload,
  CitationPayload,
  UUID,
} from '@/api/types';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

export async function submitRepo(body: RepoCreateRequest): Promise<RepoCreateResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/repos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new Error(`POST /api/v1/repos failed: ${response.status}`);
  }
  return (await response.json()) as RepoCreateResponse;
}

export async function getRepoStatus(repoId: UUID): Promise<RepoStatusResponse> {
  const response = await fetch(`${BASE_URL}/api/v1/repos/${repoId}/status`);
  if (!response.ok) {
    throw new Error(`GET /api/v1/repos/${repoId}/status failed: ${response.status}`);
  }
  return (await response.json()) as RepoStatusResponse;
}

/**
 * Streaming query — consumes the agent's SSE response.
 *
 * TODO(M2): implement an SSE parser over fetch + ReadableStream that
 *   emits typed events (one of SSEEventName) per DESIGN.md §4.3.
 *   Hand each event to a caller-supplied handler.
 */
export async function streamQuery(
  body: QueryRequest,
  onEvent: (event: QueryStreamEvent) => void,
  signal?: AbortSignal
): Promise<void> {
  const response = await fetch(`${BASE_URL}/api/v1/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  });

  if (!response.ok) {
    throw new Error(
      `POST /api/v1/query failed: ${response.status}${await response.text().then((text) => (text ? ` ${text}` : ''))}`
    );
  }

  if (!response.body) {
    throw new Error('POST /api/v1/query returned no stream body');
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { value, done } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });

    const chunks = buffer.split(/\n\n/);
    buffer = chunks.pop() ?? '';

    for (const chunk of chunks) {
      const parsed = parseSSEChunk(chunk);
      if (parsed) {
        onEvent(parsed);
      }
    }

    if (done) {
      break;
    }
  }

  if (buffer.trim()) {
    const parsed = parseSSEChunk(buffer);
    if (parsed) {
      onEvent(parsed);
    }
  }
}

function parseSSEChunk(chunk: string): QueryStreamEvent | null {
  const lines = chunk
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);

  let eventName: SSEEventName | null = null;
  const dataLines: string[] = [];

  for (const line of lines) {
    if (line.startsWith(':')) {
      continue;
    }
    if (line.startsWith('event:')) {
      eventName = line.slice('event:'.length).trim() as SSEEventName;
      continue;
    }
    if (line.startsWith('data:')) {
      dataLines.push(line.slice('data:'.length).trimStart());
    }
  }

  if (!eventName || dataLines.length === 0) {
    return null;
  }

  const payload = JSON.parse(dataLines.join('\n')) as unknown;
  return toQueryStreamEvent(eventName, payload);
}

function toQueryStreamEvent(eventName: SSEEventName, payload: unknown): QueryStreamEvent {
  switch (eventName) {
    case 'thought':
      return { event: 'thought', data: payload as ThoughtPayload };
    case 'tool_call':
      return { event: 'tool_call', data: payload as ToolCallPayload };
    case 'tool_result':
      return { event: 'tool_result', data: payload as ToolResultPayload };
    case 'citation':
      return { event: 'citation', data: payload as CitationPayload };
    case 'partial_answer':
      return { event: 'partial_answer', data: payload as PartialAnswerPayload };
    case 'final_answer':
      return { event: 'final_answer', data: payload as FinalAnswerPayload };
    case 'error':
      return { event: 'error', data: payload as ErrorPayload };
  }
}
