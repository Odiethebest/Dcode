/**
 * Typed API client — single point of contact with the gateway.
 * The SPA never calls the agent or DB directly; everything flows
 * through /api/v1/* on the gateway.
 */

import type {
  QueryRequest,
  RepoCreateRequest,
  RepoCreateResponse,
  RepoStatusResponse,
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
export async function streamQuery(_body: QueryRequest): Promise<void> {
  throw new Error('streamQuery not implemented — implement per DESIGN.md §4.3 at M2');
}
