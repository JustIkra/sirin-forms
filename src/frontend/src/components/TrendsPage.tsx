import Hero from './Hero';
import DarkPanel from './DarkPanel';

export default function TrendsPage() {
  return (
    <div
      className="grid grid-cols-1 gap-10 pt-4 lg:grid-cols-2 lg:gap-16"
      data-testid="trends-page"
    >
      <Hero
        eyebrow="ТРЕНДЫ ПРОДАЖ"
        title={
          <>
            Тренды спроса
            <br />
            по меню и
            <br />
            категориям
          </>
        }
        description="Посмотрите на историю продаж и выделите растущие и падающие позиции. Скоро здесь появятся графики за произвольный период."
      />

      <DarkPanel eyebrow="ЭКРАН ТРЕНДОВ" windowChrome>
        <div className="flex min-h-[320px] flex-col items-center justify-center gap-3 text-center">
          <div className="eyebrow-light">Скоро</div>
          <h3 className="text-xl font-semibold text-cream-100">
            Раздел в разработке
          </h3>
          <p className="max-w-xs text-sm leading-relaxed text-ink-400">
            Графики по категориям, топ-растущие и падающие позиции,
            сравнение недель — в ближайшем релизе.
          </p>
        </div>
      </DarkPanel>
    </div>
  );
}
