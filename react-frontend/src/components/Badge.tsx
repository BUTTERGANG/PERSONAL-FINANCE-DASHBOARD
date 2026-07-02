import type { ReactNode } from 'react';

interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'pos' | 'neg' | 'warn' | 'accent';
}

export default function Badge({ children, variant = 'default' }: BadgeProps) {
  return <span className={`badge${variant !== 'default' ? ` ${variant}` : ''}`}>{children}</span>;
}
