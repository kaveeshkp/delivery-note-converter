import re
from decimal import Decimal

from app.models import DeliveryData, PdfPage


class ReconciliationError(Exception):
    """Raised when the summary and packing details differ."""


NUMBER = (
    r"(?:\d{1,3}(?:,\d{3})+|\d+)"
    r"(?:\.\d+)?"
)

PACKING_HEADING_PATTERN = re.compile(
    r"\bPacking\s+List\s+No\s*:\s*P\d+\b",
    flags=re.IGNORECASE,
)

# The observed delivery summary has:
# Packing List No | Carton count | Meters | ...
SUMMARY_ENTRY_PATTERN = re.compile(
    rf"\b(?P<packing_list>P\d+)\s+"
    rf"(?P<cartons>\d+)\s+"
    rf"(?P<meters>{NUMBER})(?=\s|$)",
    flags=re.IGNORECASE,
)


def reconcile_delivery_summary(
    pages: list[PdfPage],
    delivery: DeliveryData,
) -> None:
    full_text = "\n".join(
        page.text for page in pages
    )

    first_heading = PACKING_HEADING_PATTERN.search(
        full_text
    )

    if first_heading is None:
        raise ReconciliationError(
            "Cannot locate the first Packing List section."
        )

    # Only inspect the Delivery Note section before
    # the detailed Packing List sections.
    summary_text = full_text[:first_heading.start()]

    if not re.search(
        r"\bPk\s+Lst\b",
        summary_text,
        flags=re.IGNORECASE,
    ):
        raise ReconciliationError(
            "The expected Delivery Note summary "
            "heading 'Pk Lst' was not found."
        )

    issues: list[str] = []

    summary_entries: dict[
        str,
        tuple[int, Decimal],
    ] = {}

    for line in summary_text.splitlines():
        packing_ids = re.findall(
            r"\bP\d+\b",
            line,
            flags=re.IGNORECASE,
        )

        if not packing_ids:
            continue

        matches = list(
            SUMMARY_ENTRY_PATTERN.finditer(line)
        )

        if (
            len(packing_ids) != 1
            or len(matches) != 1
        ):
            issues.append(
                "Could not reliably read a Delivery "
                f"Note summary row: {line.strip()}"
            )
            continue

        match = matches[0]

        packing_list_no = (
            match["packing_list"].upper()
        )

        if packing_list_no in summary_entries:
            issues.append(
                f"{packing_list_no}: Repeated entry "
                "in the Delivery Note summary."
            )
            continue

        carton_count = int(match["cartons"])

        meters = Decimal(
            match["meters"].replace(",", "")
        )

        summary_entries[packing_list_no] = (
            carton_count,
            meters,
        )

    if not summary_entries:
        issues.append(
            "No Packing List entries were read "
            "from the Delivery Note summary."
        )

    detail_entries = {
        packing_list.packing_list_no: packing_list
        for packing_list in delivery.packing_lists
    }

    summary_ids = set(summary_entries)
    detail_ids = set(detail_entries)

    missing_details = summary_ids - detail_ids
    unexpected_details = detail_ids - summary_ids

    for packing_list_no in sorted(missing_details):
        issues.append(
            f"{packing_list_no}: Listed in the summary "
            "but missing from the extracted details."
        )

    for packing_list_no in sorted(unexpected_details):
        issues.append(
            f"{packing_list_no}: Extracted from details "
            "but not found in the summary."
        )

    for packing_list_no in sorted(
        summary_ids & detail_ids
    ):
        expected_cartons, expected_meters = (
            summary_entries[packing_list_no]
        )

        packing_list = detail_entries[packing_list_no]

        actual_cartons = len(packing_list.records)

        actual_meters = sum(
            (
                record.mts_per_box
                for record in packing_list.records
            ),
            Decimal("0"),
        )

        if actual_cartons != expected_cartons:
            issues.append(
                f"{packing_list_no}: Summary carton "
                f"count = {expected_cartons}, "
                f"extracted count = {actual_cartons}."
            )

        if actual_meters != expected_meters:
            issues.append(
                f"{packing_list_no}: Summary meters "
                f"= {expected_meters}, "
                f"extracted Mts/Box = {actual_meters}."
            )

    # In the sample layout, Grand Total is followed
    # immediately by the document carton count.
    grand_carton_matches = re.findall(
        r"\bGrand\s+Total\s*:\s*(\d+)\b",
        summary_text,
        flags=re.IGNORECASE,
    )

    if len(grand_carton_matches) != 1:
        issues.append(
            "Expected one Grand Total carton count "
            "in the Delivery Note summary."
        )

    else:
        grand_cartons = int(
            grand_carton_matches[0]
        )

        summary_cartons = sum(
            carton_count
            for carton_count, _ in summary_entries.values()
        )

        if summary_cartons != grand_cartons:
            issues.append(
                "Summary carton counts do not add up "
                f"to the Grand Total: {summary_cartons} "
                f"versus {grand_cartons}."
            )

        if len(delivery.records) != grand_cartons:
            issues.append(
                "Extracted carton count does not match "
                f"the Grand Total: "
                f"{len(delivery.records)} "
                f"versus {grand_cartons}."
            )

    if issues:
        raise ReconciliationError(
            "Delivery Note summary reconciliation "
            "failed:\n\n"
            + "\n".join(
                f"- {issue}"
                for issue in issues
            )
        )