import type { ReactNode } from 'react';

interface StatCardProps {
  label: string;
  value: ReactNode;
  accent?: 'accent' | 'positive' | 'negative' | 'warning';
  delta?: { text: string; direction: 'up' | 'down' | 'flat' };
  // for spending, an "up" delta is bad (red); for income it's good. caller decides.
  deltaGood?: 'up' | 'down';
}

const accentVar: Record<string, string> = {
  accent: 'var(--accent)',
  positive: 'var(--positive)',
  negative: 'var(--negative)',
  warning: 'var(--warning)',
};

export default function StatCard({ label, value, accent = 'accent', delta, deltaGood = 'down' }: StatCardProps) {
  let deltaColor = 'var(--text-muted)';
  if (delta && delta.direction !== 'flat') {
    const good = delta.direction === deltaGood;
    deltaColor = good ? 'var(--positive)' : 'var(--negative)';
  }
  const arrow = delta ? (delta.direction === 'up' ? '▲' : delta.direction === 'down' ? '▼' : '→') : '';
  return (
    <div className="statcard">
      <div className="statcard-accent" style={{ background: accentVar[accent] }} />
      <div className="statcard-label">{label}</div>
      <div className="statcard-value tnum">{value}</div>
      {delta && (
        <div className="statcard-delta" style={{ color: deltaColor }}>
          <span>{arrow}</span>
          <span>{delta.text}</span>
        </div>
      )}
    </div>
  );
}
