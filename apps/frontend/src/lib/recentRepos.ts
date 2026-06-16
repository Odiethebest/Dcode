export interface RecentRepoRecord {
  repoId: string;
  url: string;
  status: string;
  savedAt: string;
}

const STORAGE_KEY = 'dcode.recent-repos';
const MAX_RECENT_REPOS = 6;

export function loadRecentRepos(): RecentRepoRecord[] {
  if (typeof window === 'undefined') {
    return [];
  }

  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return [];
    }

    const parsed = JSON.parse(raw) as unknown;
    if (!Array.isArray(parsed)) {
      return [];
    }

    return parsed.flatMap((item) => {
      if (!isRecentRepoRecord(item)) {
        return [];
      }
      return [item];
    });
  } catch {
    return [];
  }
}

export function saveRecentRepo(record: RecentRepoRecord): RecentRepoRecord[] {
  const next = [
    record,
    ...loadRecentRepos().filter((item) => item.repoId !== record.repoId),
  ].slice(0, MAX_RECENT_REPOS);

  if (typeof window !== 'undefined') {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  }

  return next;
}

function isRecentRepoRecord(value: unknown): value is RecentRepoRecord {
  if (!value || typeof value !== 'object') {
    return false;
  }

  const candidate = value as Record<string, unknown>;
  return (
    typeof candidate.repoId === 'string' &&
    typeof candidate.url === 'string' &&
    typeof candidate.status === 'string' &&
    typeof candidate.savedAt === 'string'
  );
}
