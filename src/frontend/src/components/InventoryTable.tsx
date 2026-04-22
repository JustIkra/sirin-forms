import { useState, useMemo } from 'react';
import type { InventoryItem } from '../types/forecast';

type SortKey = 'name' | 'stock' | 'need' | 'to_buy';
type SortDir = 'asc' | 'desc';

interface Props {
  items: InventoryItem[];
  emptyMessage: string;
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  if (!active) return <span className="ml-1 text-ink-600">▾</span>;
  return (
    <span className="ml-1 text-accent-500">{dir === 'asc' ? '▴' : '▾'}</span>
  );
}

function formatNum(n: number): string {
  if (n === 0) return '0';
  if (Number.isInteger(n)) return n.toLocaleString('ru-RU');
  return n.toLocaleString('ru-RU', { minimumFractionDigits: 1, maximumFractionDigits: 3 });
}

export default function InventoryTable({ items, emptyMessage }: Props) {
  const [sortKey, setSortKey] = useState<SortKey>('name');
  const [sortDir, setSortDir] = useState<SortDir>('asc');

  const toggleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortDir(key === 'name' ? 'asc' : 'desc');
    }
  };

  const sorted = useMemo(() => {
    const mul = sortDir === 'asc' ? 1 : -1;
    return [...items].sort((a, b) => {
      if (sortKey === 'name') return mul * a.product_name.localeCompare(b.product_name, 'ru');
      return mul * (a[sortKey] - b[sortKey]);
    });
  }, [items, sortKey, sortDir]);

  if (items.length === 0) {
    return (
      <div className="rounded-2xl bg-black/25 py-10 text-center text-sm text-ink-400">
        {emptyMessage}
      </div>
    );
  }

  const columns: { key: SortKey; label: string; align: string }[] = [
    { key: 'name', label: 'Ингредиент', align: 'text-left' },
    { key: 'stock', label: 'Остаток', align: 'text-right' },
    { key: 'need', label: 'Потребность', align: 'text-right' },
    { key: 'to_buy', label: 'Закупка', align: 'text-right' },
  ];

  const th =
    'px-5 py-4 text-[10px] font-semibold tracking-[0.18em] text-ink-400 uppercase cursor-pointer select-none hover:text-cream-100 transition-colors';

  return (
    <div className="overflow-hidden rounded-2xl bg-black/20">
      <table className="w-full">
        <thead>
          <tr className="border-b border-white/5">
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => toggleSort(col.key)}
                className={`${th} ${col.align}`}
              >
                {col.label}
                <SortIcon active={sortKey === col.key} dir={sortDir} />
              </th>
            ))}
            <th className="px-5 py-4 text-left text-[10px] font-semibold tracking-[0.18em] text-ink-400 uppercase">
              Ед.
            </th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((item) => (
            <tr
              key={item.product_id}
              className="border-b border-white/[0.04] transition-colors last:border-0 hover:bg-white/[0.03]"
            >
              <td className="px-5 py-4 text-sm font-medium text-cream-100">
                {item.product_name}
              </td>
              <td className="px-5 py-4 text-right text-sm tabular-nums text-cream-100">
                {formatNum(item.stock)}
              </td>
              <td className="px-5 py-4 text-right text-sm tabular-nums text-cream-100">
                {formatNum(item.need)}
              </td>
              <td
                className={`px-5 py-4 text-right text-sm font-medium tabular-nums ${
                  item.to_buy > 0 ? 'text-accent-500' : 'text-ink-500'
                }`}
              >
                {formatNum(item.to_buy)}
              </td>
              <td className="px-5 py-4 text-sm text-ink-500">
                {item.unit ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
