import type { ReactNode } from 'react';

interface CardProps {
  title?: ReactNode;
  action?: ReactNode;
  flush?: boolean; // remove body padding (for tables)
  children: ReactNode;
  className?: string;
}

export default function Card({ title, action, flush, children, className }: CardProps) {
  return (
    <div className={`card${className ? ` ${className}` : ''}`}>
      {(title || action) && (
        <div className="card-head">
          <span className="card-title">{title}</span>
          {action}
        </div>
      )}
      <div className={`card-body${flush ? ' flush' : ''}`}>{children}</div>
    </div>
  );
}
