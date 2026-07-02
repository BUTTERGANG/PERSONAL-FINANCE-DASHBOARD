interface MoneyProps {
  value: number;
  // color by sign: for spend (positive = red) vs balance (positive = green).
  // 'balance' → positive green / negative red; 'spend' → neutral; 'auto' off.
  colorize?: 'balance' | 'none';
  // force a leading sign
  signed?: boolean;
  decimals?: number;
  className?: string;
}

export function formatMoney(value: number, decimals = 2): string {
  const abs = Math.abs(value).toLocaleString('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  });
  return `${value < 0 ? '−' : ''}$${abs}`;
}

export default function Money({
  value,
  colorize = 'none',
  signed = false,
  decimals = 2,
  className,
}: MoneyProps) {
  const cls =
    colorize === 'balance' ? (value < 0 ? 'money neg' : 'money pos') : 'money';
  const display = signed && value > 0 ? `+${formatMoney(value, decimals)}` : formatMoney(value, decimals);
  return <span className={`${cls} tnum${className ? ` ${className}` : ''}`}>{display}</span>;
}
