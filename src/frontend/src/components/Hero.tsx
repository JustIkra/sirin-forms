import type { ReactNode } from 'react';

interface Props {
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  cta?: { label: string; onClick: () => void; disabled?: boolean };
  secondary?: ReactNode;
}

export default function Hero({ eyebrow, title, description, cta, secondary }: Props) {
  return (
    <section className="flex flex-col gap-8 py-6" data-testid="hero">
      <span className="eyebrow">{eyebrow}</span>

      <h2 className="hero-title text-[64px] leading-[0.95] lg:text-[80px]">
        {title}
      </h2>

      {description && (
        <p className="max-w-md text-sm leading-relaxed text-ink-600">
          {description}
        </p>
      )}

      {cta && (
        <div>
          <button
            type="button"
            onClick={cta.onClick}
            disabled={cta.disabled}
            className="btn-accent"
            data-testid="hero-cta"
          >
            {cta.label}
          </button>
        </div>
      )}

      {secondary}
    </section>
  );
}
