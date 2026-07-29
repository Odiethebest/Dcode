import { cx } from '@/lib/cx';

export type PillStatus = 'ready' | 'indexing' | 'failed';

// The three semantic buckets. Callers map the 7 repo states onto these
// (queued/cloning/parsing/embedding/graphing → indexing) and can pass a `label`
// to surface stage detail, e.g. "indexing · embedding".
const styles: Record<PillStatus, { chip: string; dot: string; label: string }> = {
  ready: { chip: 'bg-good-wash text-good', dot: 'bg-good', label: 'ready' },
  indexing: { chip: 'bg-warn-wash text-warn', dot: 'bg-warn', label: 'indexing' },
  failed: { chip: 'bg-bad-wash text-bad', dot: 'bg-bad', label: 'failed' },
};

export interface StatusPillProps {
  status: PillStatus;
  label?: string;
  className?: string;
}

export function StatusPill({ status, label, className }: StatusPillProps) {
  const s = styles[status];
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-wide',
        s.chip,
        className
      )}
    >
      <span className={cx('h-1.5 w-1.5 rounded-full', s.dot)} aria-hidden="true" />
      {label ?? s.label}
    </span>
  );
}
