import type { ReactNode } from 'react';

interface Props {
  eyebrow: string;
  title: ReactNode;
  /** Одна-строчное описание. Для нового дизайна используй `paragraphs`. */
  description?: ReactNode;
  /** Набор отдельных абзацев. Рендерятся с равным gap-4. */
  paragraphs?: ReactNode[];
  cta?: { label: string; onClick: () => void; disabled?: boolean };
  secondary?: ReactNode;
}

export default function Hero({
  eyebrow,
  title,
  description,
  paragraphs,
  cta,
  secondary,
}: Props) {
  return (
    <section
      className="flex h-full flex-col py-2"
      data-testid="hero"
    >
      <div className="flex flex-col gap-7">
        <span
          className="text-[12px] font-semibold uppercase tracking-[0.18em] text-accent-600"
          data-testid="hero-eyebrow"
        >
          {eyebrow}
        </span>
        <h2 className="hero-title text-[64px] leading-[0.95] lg:text-[88px]">
          {title}
        </h2>
      </div>

      <div className="mt-auto flex flex-col gap-7 pt-20">
        {paragraphs && paragraphs.length > 0 ? (
          <div className="flex max-w-xl flex-col gap-5 text-[20px] leading-[1.45] text-ink-600">
            {paragraphs.map((p, i) => (
              <p key={i}>{p}</p>
            ))}
          </div>
        ) : description ? (
          <p className="max-w-xl text-[20px] leading-[1.45] text-ink-600">
            {description}
          </p>
        ) : null}

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
      </div>
    </section>
  );
}
