interface ProgressBarProps {
  pct: number; // 0–100+ ; clamped to 100 for the fill width
  status?: 'ok' | 'warn' | 'over';
}

const statusColor: Record<string, string> = {
  ok: 'var(--positive)',
  warn: 'var(--warning)',
  over: 'var(--negative)',
};

export default function ProgressBar({ pct, status = 'ok' }: ProgressBarProps) {
  const width = Math.min(Math.max(pct, 0), 100);
  return (
    <div className="progress" role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100}>
      <div className="progress-fill" style={{ width: `${width}%`, background: statusColor[status] }} />
    </div>
  );
}
