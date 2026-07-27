import type { RepoStatus } from '@/api/types';

const KNOWN_REPO_STATUSES: readonly RepoStatus[] = [
  'queued',
  'cloning',
  'parsing',
  'embedding',
  'graphing',
  'ready',
  'failed',
];

/** Narrow an arbitrary string (e.g. a persisted recent-repo status) to a known RepoStatus. */
export function toKnownRepoStatus(status: string): RepoStatus {
  return (KNOWN_REPO_STATUSES as readonly string[]).includes(status)
    ? (status as RepoStatus)
    : 'queued';
}
