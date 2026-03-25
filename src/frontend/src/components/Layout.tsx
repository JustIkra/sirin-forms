import type { ReactNode } from 'react';
import type { PageId } from '../types/forecast';

const NAV_ITEMS: { id: PageId; label: string }[] = [
  { id: 'dashboard', label: 'Дашборд' },
  { id: 'forecast', label: 'Прогноз' },
  { id: 'trends', label: 'Тренды' },
  { id: 'procurement', label: 'Закупки' },
];

interface Props {
  children: ReactNode;
  activePage: PageId;
  onNavigate: (page: PageId) => void;
}

export default function Layout({ children, activePage, onNavigate }: Props) {
  return (
    <div className="flex h-screen">
      <aside className="flex w-56 flex-col border-r border-slate-200 bg-white">
        <div className="border-b border-slate-200 px-5 py-4">
          <h1 className="text-lg font-bold text-slate-900">Гурман</h1>
          <p className="text-xs text-slate-500">Аналитикс</p>
        </div>
        <nav className="flex-1 py-3">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`flex w-full items-center gap-2 px-5 py-2.5 text-left text-sm transition-colors ${
                item.id === activePage
                  ? 'bg-blue-50 font-medium text-blue-700'
                  : 'text-slate-600 hover:bg-slate-50 hover:text-slate-900'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto bg-slate-50 p-6">{children}</main>
    </div>
  );
}
