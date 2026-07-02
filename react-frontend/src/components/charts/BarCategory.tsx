import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { chartColors } from '../../theme/colors';
import { formatMoney } from '../Money';

interface BarCategoryProps {
  data: Array<{ label: string; value: number }>;
  height?: number;
  color?: string;
  layout?: 'horizontal' | 'vertical'; // vertical = horizontal bars (categories on Y)
}

const compact = (n: number) =>
  Math.abs(n) >= 1000 ? `$${(n / 1000).toFixed(0)}k` : `$${n.toFixed(0)}`;

// Single-series magnitude comparison → one accent hue, no legend (title names it).
export default function BarCategory({
  data,
  height = 260,
  color,
  layout = 'vertical',
}: BarCategoryProps) {
  const c = chartColors();
  const fill = color || c.accent;
  const horizontal = layout === 'vertical';

  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={data}
        layout={layout}
        margin={{ top: 4, right: 16, bottom: 4, left: 4 }}
        barCategoryGap={horizontal ? '28%' : '20%'}
      >
        <CartesianGrid stroke={c.grid} horizontal={!horizontal} vertical={horizontal} />
        {horizontal ? (
          <>
            <XAxis
              type="number"
              tick={{ fill: c.textMuted, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: c.grid }}
              tickFormatter={compact}
            />
            <YAxis
              type="category"
              dataKey="label"
              tick={{ fill: c.text, fontSize: 12 }}
              tickLine={false}
              axisLine={false}
              width={130}
            />
          </>
        ) : (
          <>
            <XAxis
              type="category"
              dataKey="label"
              tick={{ fill: c.text, fontSize: 11 }}
              tickLine={false}
              axisLine={{ stroke: c.grid }}
            />
            <YAxis
              type="number"
              tick={{ fill: c.textMuted, fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={compact}
              width={48}
            />
          </>
        )}
        <Tooltip
          cursor={{ fill: c.grid, opacity: 0.4 }}
          contentStyle={{
            background: c.surface,
            border: `1px solid ${c.border}`,
            borderRadius: 10,
            color: c.text,
            fontSize: 12.5,
          }}
          formatter={(v: number) => [formatMoney(v), '']}
        />
        <Bar dataKey="value" fill={fill} radius={horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0]}>
          {data.map((_, i) => (
            <Cell key={i} fill={fill} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
