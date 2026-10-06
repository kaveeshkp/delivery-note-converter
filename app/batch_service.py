from dataclasses import dataclass
from decimal import Decimal
from hashlib import sha256
from pathlib import Path
from typing import Callable

from app.models import CartonRecord, DeliveryData
from app.parser import parse_delivery
from app.pdf_reader import read_pdf
from app.validator import validate_delivery


class BatchProcessingError(Exception):
    """Raised when one or more selected PDFs fail checks."""


@dataclass(frozen=True)
class SourceDelivery:
    source_path: Path
    delivery: DeliveryData


@dataclass(frozen=True)
class BatchData:
    sources: tuple[SourceDelivery, ...]
    records: tuple[CartonRecord, ...]

    @property
    def file_count(self) -> int:
        return len(self.sources)

    @property
    def delivery_numbers(self) -> tuple[str, ...]:
        return tuple(
            dict.fromkeys(
                source.delivery.delivery_no
                for source in self.sources
            )
        )

    @property
    def delivery_count(self) -> int:
        return len(self.delivery_numbers)

    @property
    def packing_list_count(self) -> int:
        return len(
            {
                (
                    record.delivery_no,
                    record.packing_list_no,
                )
                for record in self.records
            }
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


def file_digest(path: Path) -> str:
    digest = sha256()

    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)

    return digest.hexdigest()


def validate_batch(batch: BatchData) -> None:
    if not batch.sources:
        raise BatchProcessingError(
            "No successfully processed PDFs are available."
        )

    if not batch.records:
        raise BatchProcessingError(
            "No carton rows are available for export."
        )

    expected_records = []

    for source in batch.sources:
        validate_delivery(source.delivery)
        expected_records.extend(source.delivery.records)

    if tuple(expected_records) != batch.records:
        raise BatchProcessingError(
            "Combined rows do not match the source deliveries."
        )

    seen = {}

    for source in batch.sources:
        for record in source.delivery.records:
            key = (
                record.delivery_no,
                record.packing_list_no,
                record.carton_number,
            )

            if key in seen:
                previous = seen[key]

                raise BatchProcessingError(
                    "Duplicate carton record detected.\n\n"
                    f"Delivery No: {record.delivery_no}\n"
                    f"Packing List: {record.packing_list_no}\n"
                    f"Carton: {record.carton_number}\n\n"
                    f"First file: {previous}\n"
                    f"Repeated in: {source.source_path}\n\n"
                    "Remove the overlapping file and process again."
                )

            seen[key] = source.source_path


def process_batch(
    file_paths: tuple[Path, ...],
    progress: Callable[[str], None] | None = None,
) -> BatchData:
    if not file_paths:
        raise BatchProcessingError(
            "Select at least one PDF."
        )

    sources = []
    records = []
    errors = []
    seen_hashes = {}

    for index, supplied_path in enumerate(
        file_paths,
        start=1,
    ):
        path = Path(supplied_path)

        if progress is not None:
            progress(
                f"Processing {index} of {len(file_paths)}: "
                f"{path.name}"
            )

        try:
            digest = file_digest(path)

            if digest in seen_hashes:
                raise BatchProcessingError(
                    "This PDF has the same content as:\n"
                    f"{seen_hashes[digest]}\n"
                    "Remove one of the duplicate files."
                )

            seen_hashes[digest] = path

            pages = read_pdf(path)
            delivery = parse_delivery(pages)
            validate_delivery(delivery)

            sources.append(
                SourceDelivery(
                    source_path=path,
                    delivery=delivery,
                )
            )
            records.extend(delivery.records)

        except Exception as exc:
            errors.append(
                f"FILE: {path}\n"
                f"{type(exc).__name__}: {exc}"
            )

    if errors:
        raise BatchProcessingError(
            f"{len(errors)} file(s) failed processing.\n"
            "No combined export is available.\n"
            "Correct or remove the affected files, "
            "then generate the preview again.\n\n"
            + "\n\n".join(errors)
        )

    batch = BatchData(
        sources=tuple(sources),
        records=tuple(records),
    )

    validate_batch(batch)

    return batch