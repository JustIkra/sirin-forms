"""Unit tests for MenuSnapshotService — iiko menu + stop-list capture."""
import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.iiko import IikoProduct, ProductType, SaleRecord
from app.services.menu_snapshot import MenuSnapshotService


def _dish(pid: str, in_menu: bool) -> IikoProduct:
    return IikoProduct(
        id=pid,
        name=f"Dish {pid}",
        product_type=ProductType.DISH,
        included_in_menu=in_menu,
    )


def _goods(pid: str) -> IikoProduct:
    return IikoProduct(
        id=pid,
        name=f"Goods {pid}",
        product_type=ProductType.GOODS,
        included_in_menu=True,
    )


def _sale(dish_id: str, qty: float = 1.0) -> SaleRecord:
    return SaleRecord(
        date=datetime.date(2026, 4, 22),
        dish_id=dish_id,
        dish_name=f"Dish {dish_id}",
        quantity=qty,
        price=100.0,
        total=100.0 * qty,
    )


def _make_service(
    products: list[IikoProduct],
    stop_ids: set[str],
    sales: list[SaleRecord] | None = None,
    recent_sales_days: int = 30,
) -> tuple[MenuSnapshotService, MagicMock, MagicMock, MagicMock, MagicMock]:
    iiko = MagicMock()
    iiko.get_products = AsyncMock(return_value=products)
    iiko.get_stop_list = AsyncMock(return_value=stop_ids)

    products_repo = MagicMock()
    products_repo.sync_products = AsyncMock(return_value=len(products))

    menu_repo = MagicMock()

    async def _replace(snapshot_date, rows):
        rows_list = list(rows)
        return len(rows_list)
    menu_repo.replace_snapshot = AsyncMock(side_effect=_replace)

    sales_repo = MagicMock()
    sales_repo.get_sales_by_period = AsyncMock(return_value=sales or [])

    service = MenuSnapshotService(
        iiko_client=iiko,
        products_repo=products_repo,
        menu_repo=menu_repo,
        sales_repo=sales_repo,
        recent_sales_days=recent_sales_days,
    )
    return service, iiko, products_repo, menu_repo, sales_repo


class TestMenuSnapshotService:
    async def test_snapshot_filters_to_dishes_only_with_stop_list(self):
        """Only dish-type products enter the snapshot; stop-list is applied."""
        products = [
            _dish("d1", in_menu=True),
            _dish("d2", in_menu=True),
            _dish("d3", in_menu=False),
            _goods("g1"),  # non-dish must be excluded
        ]
        service, iiko, products_repo, menu_repo, _sales_repo = _make_service(
            products=products,
            stop_ids={"d2"},
        )
        snapshot_date = datetime.date(2026, 4, 23)

        count = await service.make_snapshot(snapshot_date)

        # Call ordering: products, then sync, then stop-list, then replace
        iiko.get_products.assert_awaited_once()
        products_repo.sync_products.assert_awaited_once_with(products)
        iiko.get_stop_list.assert_awaited_once()

        # replace_snapshot called with only dishes (3 tuples, not 4)
        menu_repo.replace_snapshot.assert_awaited_once()
        called_date, called_rows = menu_repo.replace_snapshot.call_args.args
        assert called_date == snapshot_date
        rows = list(called_rows)
        by_id = {r[0]: (r[1], r[2]) for r in rows}
        assert "g1" not in by_id, "non-dish must be excluded"
        assert by_id == {
            "d1": (True, False),
            "d2": (True, True),
            "d3": (False, False),
        }
        assert count == 3

    async def test_snapshot_with_empty_stop_list(self):
        """Empty stop-list: all dishes get in_stop_list=False."""
        products = [
            _dish("d1", in_menu=True),
            _dish("d2", in_menu=False),
        ]
        service, _iiko, _products_repo, menu_repo, _sales_repo = _make_service(
            products=products,
            stop_ids=set(),
        )
        snapshot_date = datetime.date(2026, 4, 23)

        count = await service.make_snapshot(snapshot_date)

        called_rows = list(menu_repo.replace_snapshot.call_args.args[1])
        by_id = {r[0]: (r[1], r[2]) for r in called_rows}
        assert by_id == {
            "d1": (True, False),
            "d2": (False, False),
        }
        assert count == 2

    async def test_snapshot_with_no_dishes_returns_zero(self):
        """If iiko has only non-dish products, snapshot is empty."""
        products = [_goods("g1"), _goods("g2")]
        service, _iiko, _products_repo, menu_repo, _sales_repo = _make_service(
            products=products,
            stop_ids=set(),
        )
        count = await service.make_snapshot(datetime.date(2026, 4, 23))

        called_rows = list(menu_repo.replace_snapshot.call_args.args[1])
        assert called_rows == []
        assert count == 0

    async def test_recent_sales_rescue_flips_included_in_menu(self):
        """iiko flag False but dish sold recently → snapshot marks it included."""
        products = [
            _dish("d1", in_menu=True),
            _dish("kola", in_menu=False),  # iiko says not in menu...
            _dish("pivo", in_menu=False),
            _dish("dead", in_menu=False),  # ...and not sold either
        ]
        sales = [_sale("kola"), _sale("pivo", qty=3)]
        service, _iiko, _products_repo, menu_repo, sales_repo = _make_service(
            products=products,
            stop_ids=set(),
            sales=sales,
            recent_sales_days=30,
        )
        snapshot_date = datetime.date(2026, 4, 23)

        count = await service.make_snapshot(snapshot_date)

        sales_repo.get_sales_by_period.assert_awaited_once_with(
            datetime.date(2026, 3, 24),  # snapshot_date - 30
            datetime.date(2026, 4, 22),  # snapshot_date - 1
        )
        called_rows = list(menu_repo.replace_snapshot.call_args.args[1])
        by_id = {r[0]: (r[1], r[2]) for r in called_rows}
        assert by_id == {
            "d1": (True, False),
            "kola": (True, False),    # rescued by recent sale
            "pivo": (True, False),    # rescued by recent sale
            "dead": (False, False),   # not sold, stays off
        }
        assert count == 4

    async def test_stop_list_blocks_rescue(self):
        """Dish is stopped AND sold recently — stop-list wins, don't rescue.

        A stopped dish with lingering POS punches is almost always a cashier
        mistake, not real demand. Admin's stop-list decision takes priority.
        """
        products = [
            _dish("kola", in_menu=False),  # not in iiko menu...
        ]
        sales = [_sale("kola", qty=5)]  # ...but cashier punched it anyway
        service, _iiko, _products_repo, menu_repo, _sales_repo = _make_service(
            products=products,
            stop_ids={"kola"},  # and it's explicitly in the stop-list
            sales=sales,
        )
        await service.make_snapshot(datetime.date(2026, 4, 23))

        called_rows = list(menu_repo.replace_snapshot.call_args.args[1])
        by_id = {r[0]: (r[1], r[2]) for r in called_rows}
        # included=False because stop-list blocks the rescue, in_stop_list=True
        assert by_id == {"kola": (False, True)}

    async def test_iiko_flag_true_overrides_stop_list_for_included_field(self):
        """If iiko says included=True, we keep it even when stopped (tracker of
        "in menu" vs. "in stop"). get_active_dish_ids filter excludes stopped
        dishes separately."""
        products = [_dish("d1", in_menu=True)]
        service, _iiko, _products_repo, menu_repo, _sales_repo = _make_service(
            products=products,
            stop_ids={"d1"},
        )
        await service.make_snapshot(datetime.date(2026, 4, 23))

        called_rows = list(menu_repo.replace_snapshot.call_args.args[1])
        by_id = {r[0]: (r[1], r[2]) for r in called_rows}
        assert by_id == {"d1": (True, True)}

    async def test_works_without_sales_repo(self):
        """Backward compat: service still works when sales_repo is None."""
        products = [_dish("d1", in_menu=True), _dish("d2", in_menu=False)]
        iiko = MagicMock()
        iiko.get_products = AsyncMock(return_value=products)
        iiko.get_stop_list = AsyncMock(return_value=set())
        products_repo = MagicMock()
        products_repo.sync_products = AsyncMock(return_value=len(products))
        menu_repo = MagicMock()
        async def _replace(snapshot_date, rows):
            return len(list(rows))
        menu_repo.replace_snapshot = AsyncMock(side_effect=_replace)

        service = MenuSnapshotService(
            iiko_client=iiko,
            products_repo=products_repo,
            menu_repo=menu_repo,
            # sales_repo omitted
        )
        count = await service.make_snapshot(datetime.date(2026, 4, 23))

        called_rows = list(menu_repo.replace_snapshot.call_args.args[1])
        by_id = {r[0]: (r[1], r[2]) for r in called_rows}
        assert by_id == {
            "d1": (True, False),
            "d2": (False, False),  # no sales_repo → no rescue
        }
        assert count == 2

    async def test_sales_repo_failure_is_logged_and_snapshot_continues(self):
        """If recent-sales lookup throws, skip rescue — don't break snapshot."""
        products = [_dish("d1", in_menu=True), _dish("d2", in_menu=False)]
        iiko = MagicMock()
        iiko.get_products = AsyncMock(return_value=products)
        iiko.get_stop_list = AsyncMock(return_value=set())
        products_repo = MagicMock()
        products_repo.sync_products = AsyncMock(return_value=len(products))
        menu_repo = MagicMock()
        async def _replace(snapshot_date, rows):
            return len(list(rows))
        menu_repo.replace_snapshot = AsyncMock(side_effect=_replace)
        sales_repo = MagicMock()
        sales_repo.get_sales_by_period = AsyncMock(side_effect=RuntimeError("db down"))

        service = MenuSnapshotService(
            iiko_client=iiko,
            products_repo=products_repo,
            menu_repo=menu_repo,
            sales_repo=sales_repo,
        )
        count = await service.make_snapshot(datetime.date(2026, 4, 23))

        called_rows = list(menu_repo.replace_snapshot.call_args.args[1])
        by_id = {r[0]: (r[1], r[2]) for r in called_rows}
        # d2 falls back to iiko flag (False) — rescue unavailable but no crash
        assert by_id == {"d1": (True, False), "d2": (False, False)}
        assert count == 2
