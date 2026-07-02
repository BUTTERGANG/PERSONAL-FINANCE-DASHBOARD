import { Inbox } from 'lucide-react';
import type { ReactNode } from 'react';

interface EmptyStateProps {
  title?: string;
  hint?: string;
  icon?: ReactNode;
}

export default function EmptyState({ title = 'Nothing here yet', hint, icon }: EmptyStateProps) {
  return (
    <div className="empty">
      <span className="empty-icon">{icon ?? <Inbox size={28} strokeWidth={1.5} />}</span>
      <div className="empty-title">{title}</div>
      {hint && <div className="empty-hint">{hint}</div>}
    </div>
  );
}
