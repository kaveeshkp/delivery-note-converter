import sys

from PySide6.QtWidgets import QApplication

from app.batch_ui import BatchDeliveryNoteApp


def main():
    application = QApplication(sys.argv)

    application.setApplicationName(
        "Delivery Note Converter"
    )
    application.setOrganizationName(
        "DeliveryNoteConverter"
    )
    application.setStyle("Fusion")

    window = BatchDeliveryNoteApp()
    window.show()

    return application.exec()


if __name__ == "__main__":
    raise SystemExit(main())