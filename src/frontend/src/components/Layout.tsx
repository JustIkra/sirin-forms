import type { ReactNode } from 'react';
import type { PageId } from '../types/forecast';

const NAV_ITEMS: { id: PageId; label: string }[] = [
  { id: 'inventory', label: 'Остатки' },
  { id: 'trends', label: 'Тренды' },
  { id: 'forecast', label: 'Прогноз' },
];

interface Props {
  children: ReactNode;
  activePage: PageId;
  onNavigate: (page: PageId) => void;
}

export default function Layout({ children, activePage, onNavigate }: Props) {
  return (
    <div className="min-h-screen bg-cream">
      <header className="mx-auto flex max-w-[1680px] items-center justify-between px-8 pt-6 pb-4 lg:px-12">
        <div className="flex items-baseline gap-3">
          <h1 className="text-xl font-semibold tracking-tight text-ink-900">Гурман</h1>
          <span className="eyebrow">Аналитика</span>
        </div>

        <nav
          className="flex items-center gap-1 rounded-full border border-ink-900/5 bg-white/50 p-1 backdrop-blur"
          data-testid="top-nav"
        >
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              data-testid={`nav-${item.id}`}
              onClick={() => onNavigate(item.id)}
              className={
                item.id === activePage
                  ? 'chip chip-dark'
                  : 'chip chip-light'
              }
            >
              {item.label}
            </button>
          ))}
        </nav>

        <div className="w-[120px]" aria-hidden />
      </header>

      <main className="mx-auto max-w-[1680px] px-8 pb-16 pt-6 lg:px-12">
        {children}
      </main>
    </div>
  );
}
