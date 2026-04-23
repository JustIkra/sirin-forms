import type { ReactNode } from 'react';

interface Props {
  eyebrow?: string;
  children: ReactNode;
  windowChrome?: boolean;
  className?: string;
  testId?: string;
}

export default function DarkPanel({
  eyebrow,
  children,
  windowChrome = false,
  className = '',
  testId,
}: Props) {
  return (
    <section
      className={`panel relative overflow-hidden px-8 py-8 lg:px-10 lg:py-10 ${className}`}
      data-testid={testId}
    >
      {windowChrome && (
        <div className="mb-6 flex items-center gap-3 rounded-full bg-black/25 px-5 py-3">
          <span className="flex shrink-0 items-center gap-2">
            <span className="h-2.5 w-2.5 rounded-full dot-red" />
            <span className="h-2.5 w-2.5 rounded-full dot-amber" />
            <span className="h-2.5 w-2.5 rounded-full dot-green" />
          </span>
          {eyebrow && (
            <span className="eyebrow-light flex-1 pr-6 text-center">
              {eyebrow}
            </span>
          )}
        </div>
      )}
      {!windowChrome && eyebrow && (
        <div className="eyebrow-light mb-4">{eyebrow}</div>
      )}
      {children}
    </section>
  );
}
