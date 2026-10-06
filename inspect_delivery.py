from decimal import Decimal
from pathlib import Path
import sys

from app.parser import PdfParseError, parse_delivery
from app.pdf_reader import PdfReadError, read_pdf
from app.validator import (
    ValidationError,
    validate_delivery,
)


def main() -> int:
    if len(sys.argv) != 2:
        print(
            'Usage: python inspect_delivery.py '
            '"samples/your-document.pdf"'
        )
        return 1

    pdf_path = Path(sys.argv[1])

    try:
        pages = read_pdf(pdf_path)
        delivery = parse_delivery(pages)
        validate_delivery(delivery)

    except (
        PdfReadError,
        PdfParseError,
        ValidationError,
    ) as exc:
        print(f"\nERROR:\n{exc}")
        return 1

    print("\nEXTRACTION AND VALIDATION SUCCESSFUL")
    print("-" * 60)
    print(f"Delivery No: {delivery.delivery_no}")
    print(
        f"Packing Lists: {len(delivery.packing_lists)}"
    )
    print(f"Carton rows: {len(delivery.records)}")
    print(
        f"Total Mts/Box: {delivery.total_meters:,}"
    )

    print("\nPACKING LIST CHECKS")
    print("-" * 60)

    for packing_list in delivery.packing_lists:
        meters = sum(
            (
                record.mts_per_box
                for record in packing_list.records
            ),
            Decimal("0"),
        )

        print(
            f"{packing_list.packing_list_no} | "
            f"Cartons: {len(packing_list.records)} | "
            f"Mts/Box: {meters:,} | PASS"
        )

    print("\nEXTRACTED ROWS")
    print("-" * 60)

    for record in delivery.records:
        print(
            f"{record.delivery_no} | "
            f"{record.packing_list_no} | "
            f"{record.po_number} | "
            f"{record.rm_number} | "
            f"{record.carton_number} | "
            f"{record.mts_per_box}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())