import re
from decimal import Decimal

from app.models import (
    CartonRecord,
    DeliveryData,
    PackingListData,
    PdfPage,
)

from app.reconciler import (
    ReconciliationError,
    reconcile_delivery_summary,
)

class PdfParseError(Exception):
    """Raised when required PDF data cannot be extracted."""


# Accept plain numbers and correctly grouped thousands.
# Examples: 462, 4116, 4,116, 1250.50
NUMBER = (
    r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?"
)

PACKING_LIST_PATTERN = re.compile(
    r"\bPacking\s+List\s+No\s*:\s*(P\d+)\b",
    flags=re.IGNORECASE,
)

# Supported sample table structure:
# Carton | Gross | Net | M/Carton | Dimensions |
# Boxes | Box # | Net Kg/Box | Ad.Qty | Mts/Box
CARTON_ROW_PATTERN = re.compile(
    rf"^\s*"
    rf"(?P<carton>\d+)\s+"
    rf"(?P<gross>{NUMBER})\s+"
    rf"(?P<net>{NUMBER})\s+"
    rf"(?P<m_per_carton>{NUMBER})\s+"
    rf"(?P<length>{NUMBER})\s*[*x×]\s*"
    rf"(?P<width>{NUMBER})\s*[*x×]\s*"
    rf"(?P<height>{NUMBER})"
    rf"(?:\s*cm)?\s+"
    rf"(?P<boxes>\d+)\s+"
    rf"(?P<box_number>\d+)\s+"
    rf"(?P<net_per_box>{NUMBER})\s+"
    rf"(?P<adjustment>{NUMBER})\s+"
    rf"(?P<mts_per_box>{NUMBER})"
    rf"\s*$",
    flags=re.IGNORECASE,
)

TOTAL_ROW_PATTERN = re.compile(
    rf"^\s*Total\s*:\s*"
    rf"(?P<cartons>\d+)\s+"
    rf"(?P<gross>{NUMBER})\s+"
    rf"(?P<net>{NUMBER})\s+"
    rf"(?P<meters>{NUMBER})"
    rf"(?=\s|$)",
    flags=re.IGNORECASE,
)

EXPECTED_HEADERS = (
    r"Carton\s*#.*"
    r"Gross\s+Kg.*"
    r"Net\s+Kg.*"
    r"M/Carton.*"
    r"Carton\s+Size.*"
    r"Boxes.*"
    r"Box\s*#.*"
    r"Net\s+Kg/Box.*"
    r"Ad\.?\s*Qty.*"
    r"Mts/Box"
)


def to_decimal(value: str) -> Decimal:
    return Decimal(value.replace(",", ""))


def get_required_field(
    pattern: str,
    text: str,
    field_name: str,
    packing_list_no: str,
) -> str:
    matches = re.findall(
        pattern,
        text,
        flags=re.IGNORECASE,
    )

    unique_values = list(dict.fromkeys(matches))

    if len(unique_values) != 1:
        raise PdfParseError(
            f"{packing_list_no}: Expected one "
            f"{field_name}, found {len(unique_values)}."
        )

    return unique_values[0]


def parse_packing_list(
    delivery_no: str,
    packing_list_no: str,
    block: str,
) -> PackingListData:
    parts = re.split(
        r"\bPacking\s+Details\b",
        block,
        maxsplit=1,
        flags=re.IGNORECASE,
    )

    if len(parts) != 2:
        raise PdfParseError(
            f"{packing_list_no}: "
            "Packing Details section was not found."
        )

    master_information, details = parts

    po_number = get_required_field(
        r"\bP\.?\s*O\.?\s+Number\s*:\s*(\d+)\b",
        master_information,
        "P.O Number",
        packing_list_no,
    )

    rm_number = get_required_field(
        r"\bRM\s*#\s*:\s*(\d+)\b",
        master_information,
        "RM #",
        packing_list_no,
    )

    records: list[CartonRecord] = []

    header_found = False
    total_match = None

    for raw_line in details.splitlines():
        line = raw_line.strip()

        if not line:
            continue

        if re.search(
            EXPECTED_HEADERS,
            line,
            flags=re.IGNORECASE,
        ):
            header_found = True
            continue

        if not header_found:
            continue

        if re.match(
            r"^Total\s*:",
            line,
            flags=re.IGNORECASE,
        ):
            total_match = TOTAL_ROW_PATTERN.match(line)

            if total_match is None:
                raise PdfParseError(
                    f"{packing_list_no}: "
                    f"Could not read the Total row: {line}"
                )

            break

        row_match = CARTON_ROW_PATTERN.fullmatch(line)

        if row_match is not None:
            # Version 1 is restricted to the observed
            # one-box-per-carton sample layout.
            if int(row_match["boxes"]) != 1:
                raise PdfParseError(
                    f"{packing_list_no}: Carton "
                    f"{row_match['carton']} has multiple "
                    "boxes. This layout needs review."
                )

            records.append(
                CartonRecord(
                    delivery_no=delivery_no,
                    packing_list_no=packing_list_no,
                    po_number=po_number,
                    rm_number=rm_number,
                    carton_number=row_match["carton"],
                    mts_per_box=to_decimal(
                        row_match["mts_per_box"]
                    ),
                )
            )

            continue

        # Do not silently skip a numeric table row
        # that may contain carton data.
        if re.match(r"^\d", line):
            raise PdfParseError(
                f"{packing_list_no}: "
                f"Unrecognized packing detail row: {line}"
            )

    if not header_found:
        raise PdfParseError(
            f"{packing_list_no}: "
            "The expected Packing Details columns "
            "were not found."
        )

    if not records:
        raise PdfParseError(
            f"{packing_list_no}: "
            "No carton rows were extracted."
        )

    if total_match is None:
        raise PdfParseError(
            f"{packing_list_no}: "
            "The Packing Details Total row "
            "was not found."
        )

    return PackingListData(
        packing_list_no=packing_list_no,
        records=tuple(records),
        expected_cartons=int(total_match["cartons"]),
        expected_meters=to_decimal(
            total_match["meters"]
        ),
    )


def parse_delivery(
    pages: list[PdfPage],
) -> DeliveryData:
    full_text = "\n".join(
        page.text for page in pages
    )

    delivery_numbers = list(
        dict.fromkeys(
            re.findall(
                r"\bDelivery\s+No\s*:\s*(\d+)\b",
                full_text,
                flags=re.IGNORECASE,
            )
        )
    )

    if len(delivery_numbers) != 1:
        raise PdfParseError(
            "Expected exactly one Delivery No, "
            f"found {len(delivery_numbers)}."
        )

    # Keep the original string, including leading zeros.
    delivery_no = delivery_numbers[0]

    headings = list(
        PACKING_LIST_PATTERN.finditer(full_text)
    )

    if not headings:
        raise PdfParseError(
            "No Packing List sections were found."
        )

    packing_lists: list[PackingListData] = []
    seen_packing_lists: set[str] = set()

    for index, heading in enumerate(headings):
        packing_list_no = heading.group(1).upper()

        if packing_list_no in seen_packing_lists:
            raise PdfParseError(
                f"{packing_list_no}: Repeated Packing "
                "List heading. Review the document "
                "before processing."
            )

        seen_packing_lists.add(packing_list_no)

        block_end = (
            headings[index + 1].start()
            if index + 1 < len(headings)
            else len(full_text)
        )

        block = full_text[
            heading.end():block_end
        ]

        packing_lists.append(
            parse_packing_list(
                delivery_no=delivery_no,
                packing_list_no=packing_list_no,
                block=block,
            )
        )


    delivery = DeliveryData(
        delivery_no=delivery_no,
        packing_lists=tuple(packing_lists),
    )

    try:
        reconcile_delivery_summary(
            pages,
            delivery,
        )

    except ReconciliationError as exc:
        raise PdfParseError(str(exc)) from exc

    return delivery