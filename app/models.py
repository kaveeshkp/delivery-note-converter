from dataclasses import dataclass
from decimal import Decimal


EXCEL_HEADERS = (
    "Delivery No:",
    "Packing List No",
    "P.O Number",
    "RM #",
    "Carton #",
    "Mts/Box",
)


@dataclass(frozen=True)
class PdfPage:
    page_number: int
    text: str
    layout_text: str


@dataclass(frozen=True)
class CartonRecord:
    delivery_no: str
    packing_list_no: str
    po_number: str
    rm_number: str
    carton_number: str
    mts_per_box: Decimal


@dataclass(frozen=True)
class PackingListData:
    packing_list_no: str
    records: tuple[CartonRecord, ...]
    expected_cartons: int
    expected_meters: Decimal


@dataclass(frozen=True)
class DeliveryData:
    delivery_no: str
    packing_lists: tuple[PackingListData, ...]

    @property
    def records(self) -> tuple[CartonRecord, ...]:
        return tuple(
            record
            for packing_list in self.packing_lists
            for record in packing_list.records
        )

    @property
    def total_meters(self) -> Decimal:
        return sum(
            (
                record.mts_per_box
                for record in self.records
            ),
            Decimal("0"),
        )