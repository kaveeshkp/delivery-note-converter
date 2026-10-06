from decimal import Decimal

from app.models import DeliveryData


class ValidationError(Exception):
    """Raised when extracted data fails validation."""


def validate_delivery(delivery: DeliveryData) -> None:
    issues: list[str] = []
    seen_records: set[tuple[str, str]] = set()

    if not delivery.delivery_no.strip():
        issues.append("Delivery No is missing.")

    if not delivery.packing_lists:
        issues.append("No Packing Lists were extracted.")

    for packing_list in delivery.packing_lists:
        packing_list_no = packing_list.packing_list_no
        records = packing_list.records

        if len(records) != packing_list.expected_cartons:
            issues.append(
                f"{packing_list_no}: Carton count "
                f"mismatch. PDF total = "
                f"{packing_list.expected_cartons}, "
                f"extracted rows = {len(records)}."
            )

        actual_meters = sum(
            (
                record.mts_per_box
                for record in records
            ),
            Decimal("0"),
        )

        if actual_meters != packing_list.expected_meters:
            issues.append(
                f"{packing_list_no}: Quantity mismatch. "
                f"PDF total = "
                f"{packing_list.expected_meters}, "
                f"extracted Mts/Box total = "
                f"{actual_meters}."
            )

        for record in records:
            required_fields = {
                "Delivery No": record.delivery_no,
                "Packing List No": record.packing_list_no,
                "P.O Number": record.po_number,
                "RM #": record.rm_number,
                "Carton #": record.carton_number,
            }

            for field_name, value in required_fields.items():
                if not value.strip():
                    issues.append(
                        f"{packing_list_no}: "
                        f"{field_name} is missing."
                    )

            if record.delivery_no != delivery.delivery_no:
                issues.append(
                    f"{packing_list_no}: "
                    "Delivery No does not match "
                    "the document."
                )

            if record.packing_list_no != packing_list_no:
                issues.append(
                    f"{packing_list_no}: A carton row "
                    "belongs to a different Packing List."
                )

            if not record.mts_per_box.is_finite():
                issues.append(
                    f"{packing_list_no}, carton "
                    f"{record.carton_number}: "
                    "Mts/Box must be a finite number."
                )

            elif record.mts_per_box < 0:
                issues.append(
                    f"{packing_list_no}, carton "
                    f"{record.carton_number}: "
                    "Mts/Box cannot be negative."
                )

            key = (
                record.packing_list_no,
                record.carton_number,
            )

            if key in seen_records:
                issues.append(
                    f"{packing_list_no}: Duplicate carton "
                    f"{record.carton_number}."
                )

            seen_records.add(key)

    if issues:
        raise ValidationError(
            "Validation failed:\n\n"
            + "\n".join(
                f"- {issue}"
                for issue in issues
            )
        )