import { useState, useMemo } from 'react';
import type { InventoryItem } from '../types/forecast';

type SortKey = 'name' | 'stock' | 'need' | 'to_buy';
type SortDir = 'asc' | 'desc';

interface Props {
  items: InventoryItem[];
  emptyMessage: string;
}

function SortIcon({ active, dir }: { active: boolean; dir: SortDir }) {
  return (
    <span className="ml-1 text-[10px]">
      {active ? (dir === 'asc' ? '▲' : '▼') : '▼'}
    </span>
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
      <div className="glass-card p-8 text-center text-sm text-slate-400">
        {emptyMessage}
      </div>
    );
  }

  const columns: { key: SortKey; label: string; align: string }[] = [
    { key: 'name', label: 'Ингредиент', align: 'text-left' },
    { key: 'stock', label: 'Остаток', align: 'text-right' },
    { key: 'need', label: 'Потребность', align: 'text-right' },
    { key: 'to_buy', label: 'Закупить', align: 'text-right' },
  ];

  return (
    <div className="glass-card overflow-hidden">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-white/[0.06]">
            {columns.map((col) => (
              <th
                key={col.key}
                onClick={() => toggleSort(col.key)}
                className={`cursor-pointer select-none px-4 py-3 font-medium text-slate-400 transition-colors hover:text-slate-200 ${col.align}`}
              >
                {col.label}
                <SortIcon active={sortKey === col.key} dir={sortDir} />
              </th>
            ))}
            <th className="px-4 py-3 text-left font-medium text-slate-400">Ед.</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((item) => (
            <tr
              key={item.product_id}
              className="border-b border-white/[0.03] transition-colors hover:bg-white/[0.02]"
            >
              <td className="px-4 py-2.5 text-white">{item.product_name}</td>
              <td className="px-4 py-2.5 text-right tabular-nums text-slate-300">
                {formatNum(item.stock)}
              </td>
              <td className="px-4 py-2.5 text-right tabular-nums text-slate-300">
                {formatNum(item.need)}
              </td>
              <td className={`px-4 py-2.5 text-right tabular-nums font-medium ${
                item.to_buy > 0 ? 'text-orange-400' : 'text-slate-500'
              }`}>
                {formatNum(item.to_buy)}
              </td>
              <td className="px-4 py-2.5 text-slate-500 text-sm">
                {item.unit ?? '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
