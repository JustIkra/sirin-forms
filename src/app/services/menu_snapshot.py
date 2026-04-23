"""MenuSnapshotService — Domain 1 daily capture of iiko menu + stop-list.

Run at 04:00 MSK (see `main.py:_daily_retrain_loop`) and once on startup
if `menu_snapshots` is empty. Downstream ML training and forecast pipelines
read `menu_snapshots` — never live iiko — to decide which dishes are
currently in the menu and which are stopped.
"""
import datetime
import logging

from app.clients.iiko import IikoClient
from app.repositories.menu_snapshots import MenuSnapshotsRepository
from app.repositories.products import ProductsRepository
from app.repositories.sales import SalesRepository

logger = logging.getLogger(__name__)


class MenuSnapshotService:
    """Capture the current iiko menu + stop-list into `menu_snapshots`."""

    def __init__(
        self,
        iiko_client: IikoClient,
        products_repo: ProductsRepository,
        menu_repo: MenuSnapshotsRepository,
        sales_repo: SalesRepository | None = None,
        recent_sales_days: int = 30,
    ) -> None:
        self._iiko = iiko_client
        self._products_repo = products_repo
        self._menu_repo = menu_repo
        self._sales_repo = sales_repo
        self._recent_sales_days = recent_sales_days

    async def make_snapshot(self, snapshot_date: datetime.date) -> int:
        """Snapshot iiko menu + stop-list for `snapshot_date`.

        Steps:
          1. Fetch all products from iiko.
          2. `products_repo.sync_products(...)` — refresh FK target so newly
             added dishes don't break the `menu_snapshots.dish_id` FK.
          3. Fetch the delivery stop-list (graceful: returns empty on failure).
          4. If a sales repo is configured, fetch recent-sales dish_ids so we
             can rescue dishes that iiko admin left as
             `defaultIncludedInMenu=false` but that are actively selling
             (e.g. Кола/Пиво sold via POS but absent from delivery menu).
             A dish in the stop-list is NOT rescued: stop-list is an explicit
             admin decision, and lingering POS punches for it are more likely
             human error than active demand.
          5. Filter to `product_type == "dish"` only (goods/modifiers excluded).
          6. Replace the snapshot for that date with fresh rows.

        Returns the number of rows written.
        """
        products = await self._iiko.get_products()
        await self._products_repo.sync_products(products)

        stop_ids = await self._iiko.get_stop_list()
        recently_sold = await self._recent_sold_dish_ids(snapshot_date)

        rescued = 0
        rows: list[tuple[str, bool, bool]] = []
        for p in products:
            if p.product_type != "dish":
                continue
            in_stop = p.id in stop_ids
            iiko_included = bool(p.included_in_menu)
            sold_recently = p.id in recently_sold
            # Stop-list wins over recent sales: a dish that is stopped is
            # off the menu by admin decision, and any lingering POS punches
            # for it are more likely human error than active demand.
            effective_included = iiko_included or (sold_recently and not in_stop)
            if not iiko_included and sold_recently and not in_stop:
                rescued += 1
            rows.append((p.id, effective_included, in_stop))

        count = await self._menu_repo.replace_snapshot(snapshot_date, rows)
        logger.info(
            "menu snapshot %s: %d dishes (of %d products), %d in stop-list, "
            "%d rescued via recent sales",
            snapshot_date, len(rows), len(products), len(stop_ids), rescued,
        )
        return count

    async def _recent_sold_dish_ids(
        self, snapshot_date: datetime.date,
    ) -> set[str]:
        """Return dish_ids with any sales in the last `recent_sales_days`.

        Used to mark dishes as "in menu" when iiko's own flag lags behind
        actual POS activity. Returns an empty set gracefully when no sales
        repo is wired or the query fails — we'd rather miss the rescue
        than break the snapshot.
        """
        if self._sales_repo is None or self._recent_sales_days <= 0:
            return set()
        date_from = snapshot_date - datetime.timedelta(
            days=self._recent_sales_days,
        )
        date_to = snapshot_date - datetime.timedelta(days=1)
        try:
            sales = await self._sales_repo.get_sales_by_period(
                date_from, date_to,
            )
        except Exception:
            logger.warning(
                "recent-sales lookup failed for snapshot %s, skipping rescue",
                snapshot_date, exc_info=True,
            )
            return set()
        return {s.dish_id for s in sales if s.dish_id and s.quantity > 0}
