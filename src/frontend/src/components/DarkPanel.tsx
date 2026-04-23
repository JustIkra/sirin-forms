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
      className={`panel relative overflow-hidden px-8 py-7 lg:px-10 lg:py-9 ${className}`}
      data-testid={testId}
    >
      {windowChrome && (
        <div className="mb-4 flex items-center gap-2">
          <span className="h-3 w-3 rounded-full dot-red" />
          <span className="h-3 w-3 rounded-full dot-amber" />
          <span className="h-3 w-3 rounded-full dot-green" />
          {eyebrow && (
            <span className="eyebrow-light ml-3">{eyebrow}</span>
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
