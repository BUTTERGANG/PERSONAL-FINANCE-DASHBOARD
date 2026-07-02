import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { chartColors } from '../../theme/colors';
import { formatMoney } from '../Money';

interface AreaTrendProps {
  data: Array<Record<string, unknown>>;
  xKey: string;
  yKey: string;
  height?: number;
  color?: string; // defaults to accent
  // compact currency for axis ticks
  yLabel?: string;
}

const compact = (n: number) =>
  Math.abs(n) >= 1000 ? `$${(n / 1000).toFixed(0)}k` : `$${n.toFixed(0)}`;

export default function AreaTrend({ data, xKey, yKey, height = 240, color }: AreaTrendProps) {
  const c = chartColors();
  const stroke = color || c.accent;
  const gradId = `grad-${yKey}`;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <AreaChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: 4 }}>
        <defs>
          <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={stroke} stopOpacity={0.22} />
            <stop offset="100%" stopColor={stroke} stopOpacity={0.02} />
          </linearGradient>
        </defs>
        <CartesianGrid stroke={c.grid} vertical={false} />
        <XAxis
          dataKey={xKey}
          tick={{ fill: c.textMuted, fontSize: 11 }}
          tickLine={false}
          axisLine={{ stroke: c.grid }}
          minTickGap={28}
        />
        <YAxis
          tick={{ fill: c.textMuted, fontSize: 11 }}
          tickLine={false}
          axisLine={false}
          tickFormatter={compact}
          width={48}
        />
        <Tooltip
          contentStyle={{
            background: c.surface,
            border: `1px solid ${c.border}`,
            borderRadius: 10,
            color: c.text,
            fontSize: 12.5,
            boxShadow: '0 8px 24px rgba(16,24,40,0.12)',
          }}
          labelStyle={{ color: c.textMuted, marginBottom: 4 }}
          formatter={(v: number) => [formatMoney(v), '']}
        />
        <Area
          type="monotone"
          dataKey={yKey}
          stroke={stroke}
          strokeWidth={2}
          fill={`url(#${gradId})`}
          dot={false}
          activeDot={{ r: 4, strokeWidth: 0 }}
        />
      </AreaChart>
    </ResponsiveContainer>
  );
}
