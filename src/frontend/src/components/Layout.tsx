import type { ReactNode } from 'react';
import type { PageId } from '../types/forecast';

const NAV_ITEMS: { id: PageId; label: string }[] = [
  { id: 'forecast', label: 'Прогноз' },
  { id: 'inventory', label: 'Остатки' },
];

interface Props {
  children: ReactNode;
  activePage: PageId;
  onNavigate: (page: PageId) => void;
}

export default function Layout({ children, activePage, onNavigate }: Props) {
  return (
    <div className="flex h-screen">
      <aside className="flex w-56 flex-col border-r border-white/[0.06] bg-[#0f0f0f]">
        <div className="border-b border-white/[0.06] px-5 py-4">
          <h1 className="text-lg font-bold text-white">Гурман</h1>
          <p className="text-xs text-slate-400">Аналитикс</p>
        </div>
        <nav className="flex-1 py-3">
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              onClick={() => onNavigate(item.id)}
              className={`flex w-full items-center gap-2 px-5 py-2.5 text-left text-sm transition-colors ${
                item.id === activePage
                  ? 'border-l-2 border-blue-400 bg-white/[0.08] font-medium text-white'
                  : 'border-l-2 border-transparent text-slate-400 hover:bg-white/[0.04] hover:text-white'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto bg-[#0a0a0a] p-6">{children}</main>
    </div>
  );
}
