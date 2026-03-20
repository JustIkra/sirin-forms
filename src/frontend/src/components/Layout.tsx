import type { ReactNode } from 'react';

const NAV_ITEMS = [
  { id: 'wf01', label: 'Дашборд', disabled: true },
  { id: 'wf02', label: 'Продажи', disabled: true },
  { id: 'wf03', label: 'Прогноз', disabled: false },
  { id: 'wf04', label: 'Закупки', disabled: true },
  { id: 'wf05', label: 'План-факт', disabled: true },
  { id: 'wf06', label: 'Настройки', disabled: true },
];

interface Props {
  children: ReactNode;
}

export default function Layout({ children }: Props) {
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
              disabled={item.disabled}
              className={`flex w-full items-center gap-2 px-5 py-2.5 text-left text-sm transition-colors ${
                item.disabled
                  ? 'cursor-not-allowed text-slate-400'
                  : 'bg-blue-50 font-medium text-blue-700'
              }`}
            >
              {item.label}
              {item.disabled && (
                <span className="ml-auto rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-400">
                  скоро
                </span>
              )}
            </button>
          ))}
        </nav>
      </aside>
      <main className="flex-1 overflow-y-auto bg-slate-50 p-6">{children}</main>
    </div>
  );
}
