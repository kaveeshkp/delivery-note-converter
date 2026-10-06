from pathlib import Path

import pdfplumber

from app.models import PdfPage


class PdfReadError(Exception):
    """Raised when the application cannot read a PDF."""


def read_pdf(file_path: str | Path) -> list[PdfPage]:
    path = Path(file_path)

    if not path.exists():
        raise PdfReadError(
            f"PDF file was not found: {path}"
        )

    if not path.is_file():
        raise PdfReadError(
            "The selected path is not a file."
        )

    if path.suffix.lower() != ".pdf":
        raise PdfReadError(
            "Please select a file with the .pdf extension."
        )

    pages: list[PdfPage] = []

    try:
        with pdfplumber.open(path) as pdf:
            if not pdf.pages:
                raise PdfReadError(
                    "The selected PDF contains no pages."
                )

            for page_number, page in enumerate(
                pdf.pages,
                start=1,
            ):
                text = page.extract_text(
                    layout=False,
                    x_tolerance=2,
                    y_tolerance=3,
                ) or ""

                layout_text = page.extract_text(
                    layout=True,
                    x_tolerance=2,
                    y_tolerance=3,
                ) or ""

                pages.append(
                    PdfPage(
                        page_number=page_number,
                        text=text,
                        layout_text=layout_text,
                    )
                )

    except PdfReadError:
        raise

    except Exception as exc:
        raise PdfReadError(
            "Could not read the PDF. It may be damaged, "
            "password-protected, or unsupported. "
            f"Details: {exc}"
        ) from exc

    if not any(page.text.strip() for page in pages):
        raise PdfReadError(
            "No readable text was found in this PDF. "
            "It may be a scanned or image-only document. "
            "This version requires a text-based PDF."
        )

    return pages