import type { RepoStatus, StageState } from '@/api/types';

const repoStatusClasses: Record<RepoStatus, string> = {
  queued: 'bg-stone-200 text-stone-800',
  cloning: 'bg-sky-100 text-sky-800',
  parsing: 'bg-sky-100 text-sky-800',
  embedding: 'bg-sky-100 text-sky-800',
  graphing: 'bg-sky-100 text-sky-800',
  ready: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-rose-100 text-rose-800',
};

const stageStateClasses: Record<StageState, string> = {
  pending: 'bg-stone-200 text-stone-700',
  in_progress: 'bg-amber-100 text-amber-800',
  done: 'bg-emerald-100 text-emerald-800',
  failed: 'bg-rose-100 text-rose-800',
};

interface RepoStatusBadgeProps {
  value: RepoStatus | StageState;
}

export function RepoStatusBadge({ value }: RepoStatusBadgeProps) {
  const classes =
    value in repoStatusClasses
      ? repoStatusClasses[value as RepoStatus]
      : stageStateClasses[value as StageState];

  return (
    <span
      className={`inline-flex min-w-20 justify-center rounded-md px-2 py-1 text-xs font-medium uppercase tracking-wide ${classes}`}
    >
      {value.replace('_', ' ')}
    </span>
  );
}
