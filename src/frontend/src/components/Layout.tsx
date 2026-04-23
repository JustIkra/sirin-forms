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
      <header className="mx-auto grid max-w-[1680px] grid-cols-1 items-center gap-10 px-8 pt-8 pb-6 lg:grid-cols-2 lg:gap-16 lg:px-12">
        <div className="flex items-baseline gap-3">
          <h1 className="text-[22px] font-semibold tracking-tight text-ink-900">Гурман</h1>
          <span className="eyebrow">Аналитикс</span>
        </div>

        <nav
          className="flex w-full items-center justify-between gap-1 rounded-full border border-ink-900/5 bg-white/70 p-1.5 backdrop-blur"
          data-testid="top-nav"
        >
          {NAV_ITEMS.map((item) => (
            <button
              key={item.id}
              data-testid={`nav-${item.id}`}
              onClick={() => onNavigate(item.id)}
              className={
                'chip flex-1 justify-center !px-8 !py-3 !text-[15px] !font-medium ' +
                (item.id === activePage ? 'chip-dark' : 'chip-light')
              }
            >
              {item.label}
            </button>
          ))}
        </nav>
      </header>

      <main className="mx-auto max-w-[1680px] px-8 pb-16 pt-2 lg:px-12">
        {children}
      </main>
    </div>
  );
}
