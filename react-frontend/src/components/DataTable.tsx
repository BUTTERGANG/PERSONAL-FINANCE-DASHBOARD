import { useMemo, useState, type ReactNode } from 'react';
import EmptyState from './EmptyState';

export interface Column<T> {
  key: string;
  header: string;
  numeric?: boolean;
  sortable?: boolean;
  // value used for sorting (defaults to the raw field at `key` if it exists)
  sortValue?: (row: T) => number | string;
  render: (row: T) => ReactNode;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string;
  empty?: { title?: string; hint?: string };
}

export default function DataTable<T>({ columns, rows, rowKey, empty }: DataTableProps<T>) {
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' } | null>(null);

  const sorted = useMemo(() => {
    if (!sort) return rows;
    const col = columns.find((c) => c.key === sort.key);
    if (!col?.sortValue) return rows;
    const factor = sort.dir === 'asc' ? 1 : -1;
    return [...rows].sort((a, b) => {
      const av = col.sortValue!(a);
      const bv = col.sortValue!(b);
      if (av < bv) return -1 * factor;
      if (av > bv) return 1 * factor;
      return 0;
    });
  }, [rows, sort, columns]);

  function toggleSort(key: string) {
    setSort((s) =>
      s?.key === key ? { key, dir: s.dir === 'asc' ? 'desc' : 'asc' } : { key, dir: 'desc' },
    );
  }

  if (rows.length === 0) {
    return <EmptyState title={empty?.title ?? 'No data'} hint={empty?.hint} />;
  }

  return (
    <div className="table-wrap">
      <table className="dtable">
        <thead>
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                className={`${c.numeric ? 'num' : ''} ${c.sortable && c.sortValue ? 'sortable' : ''}`}
                onClick={c.sortable && c.sortValue ? () => toggleSort(c.key) : undefined}
              >
                {c.header}
                {sort?.key === c.key ? (sort.dir === 'asc' ? ' ↑' : ' ↓') : ''}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={rowKey(row)}>
              {columns.map((c) => (
                <td key={c.key} className={c.numeric ? 'num' : ''}>
                  {c.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
