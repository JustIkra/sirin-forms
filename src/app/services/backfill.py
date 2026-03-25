import datetime
import logging

from app.clients.iiko import IikoClient
from app.models.iiko import OlapReportType, OlapV2Request
from app.repositories.sales import SalesRepository
from app.services.data_collector import DataCollector

logger = logging.getLogger(__name__)


class BackfillService:

    def __init__(
        self,
        iiko_client: IikoClient,
        sales_repo: SalesRepository,
    ) -> None:
        self._iiko = iiko_client
        self._sales_repo = sales_repo

    async def backfill(
        self,
        date_from: datetime.date,
        date_to: datetime.date,
        chunk_days: int = 30,
    ) -> dict:
        """Fetch historical sales from iiko in chunks and save to DB."""
        total_records = 0
        chunks_ok = 0
        chunks_failed = 0
        current = date_from

        while current <= date_to:
            chunk_end = min(current + datetime.timedelta(days=chunk_days - 1), date_to)
            try:
                report = await self._iiko.get_olap_report_v2(
                    OlapV2Request(
                        report_type=OlapReportType.SALES,
                        date_from=current,
                        date_to=chunk_end,
                        group_by_row_fields=["DishName", "DishId", "OpenDate.Typed"],
                        aggregate_fields=["DishAmountInt", "DishSumInt"],
                        filters={"OpenDate.Typed": {
                            "filterType": "DateRange",
                            "periodType": "CUSTOM",
                            "from": current.isoformat(),
                            "to": chunk_end.isoformat(),
                            "includeLow": True,
                            "includeHigh": True,
                        }},
                    ),
                )
                sales = DataCollector._parse_olap_sales(report.data)
                if sales:
                    count = await self._sales_repo.bulk_upsert_sales(sales)
                    total_records += count
                    logger.info(
                        "Backfill %s — %s: %d records",
                        current, chunk_end, count,
                    )
                chunks_ok += 1
            except Exception as exc:
                logger.error(
                    "Backfill chunk %s — %s failed: %s",
                    current, chunk_end, exc, exc_info=True,
                )
                chunks_failed += 1

            current = chunk_end + datetime.timedelta(days=1)

        return {
            "total_records": total_records,
            "chunks_ok": chunks_ok,
            "chunks_failed": chunks_failed,
            "date_from": date_from.isoformat(),
            "date_to": date_to.isoformat(),
        }
