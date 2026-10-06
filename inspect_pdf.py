from pathlib import Path
import re
import sys

from app.pdf_reader import PdfReadError, read_pdf


def main() -> int:
    if len(sys.argv) != 2:
        print(
            'Usage: python inspect_pdf.py '
            '"samples/your-document.pdf"'
        )
        return 1

    pdf_path = Path(sys.argv[1])

    try:
        pages = read_pdf(pdf_path)

    except PdfReadError as exc:
        print(f"\nERROR: {exc}")
        return 1

    full_text = "\n".join(
        page.text for page in pages
    )

    delivery_numbers = list(
        dict.fromkeys(
            re.findall(
                r"\bDelivery\s+No\s*:\s*(\d+)",
                full_text,
                flags=re.IGNORECASE,
            )
        )
    )

    packing_list_numbers = re.findall(
        r"\bPacking\s+List\s+No\s*:\s*(P\d+)",
        full_text,
        flags=re.IGNORECASE,
    )

    unique_packing_lists = list(
        dict.fromkeys(
            number.upper()
            for number in packing_list_numbers
        )
    )

    empty_pages = [
        str(page.page_number)
        for page in pages
        if not page.text.strip()
    ]

    output_directory = (
        Path(__file__).resolve().parent / "output"
    )
    output_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    text_output = (
        output_directory / "extracted_text.txt"
    )
    layout_output = (
        output_directory / "extracted_layout.txt"
    )

    try:
        text_output.write_text(
            "\n\n".join(
                f"===== PAGE {page.page_number} =====\n"
                f"{page.text}"
                for page in pages
            ),
            encoding="utf-8",
        )

        layout_output.write_text(
            "\n\n".join(
                f"===== PAGE {page.page_number} =====\n"
                f"{page.layout_text}"
                for page in pages
            ),
            encoding="utf-8",
        )

    except OSError as exc:
        print(
            "\nERROR: Could not save the "
            f"inspection files: {exc}"
        )
        return 1

    print("\nPDF READ SUCCESSFUL")
    print("-" * 45)
    print(f"File: {pdf_path.name}")
    print(f"Pages: {len(pages)}")

    print(
        "Delivery No: "
        + (
            ", ".join(delivery_numbers)
            if delivery_numbers
            else "NOT FOUND"
        )
    )

    print(
        "Packing List headings found: "
        f"{len(packing_list_numbers)}"
    )

    print(
        "Unique Packing Lists: "
        f"{len(unique_packing_lists)}"
    )

    print(
        "Pages without readable text: "
        + (
            ", ".join(empty_pages)
            if empty_pages
            else "None"
        )
    )

    print("\nPacking List numbers:")

    for number in unique_packing_lists:
        print(f"  {number}")

    print("\nInspection files saved:")
    print(f"  {text_output}")
    print(f"  {layout_output}")

    print(
        "\nThis checks PDF reading only. "
        "Carton extraction and total validation "
        "will be added next."
    )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())