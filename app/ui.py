import math
from pathlib import Path
from queue import Empty, Queue
from threading import Thread

from PySide6.QtCore import (
    QPointF,
    QRectF,
    QSettings,
    QSize,
    QTimer,
    Qt,
    QUrl,
)
from PySide6.QtGui import (
    QColor,
    QDesktopServices,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.excel_exporter import export_delivery
from app.models import EXCEL_HEADERS
from app.parser import parse_delivery
from app.pdf_reader import read_pdf
from app.themes import apply_theme, contrasting_text
from app.validator import validate_delivery


def make_label(text="", name=None):
    widget = QLabel(text)
    widget.setTextFormat(Qt.TextFormat.PlainText)

    if name:
        widget.setObjectName(name)

    return widget


def make_button(text, callback, primary=False):
    widget = QPushButton(text)

    if primary:
        widget.setObjectName("Primary")

    widget.setCursor(
        Qt.CursorShape.PointingHandCursor
    )
    widget.clicked.connect(callback)

    return widget


def make_card(name="Card"):
    frame = QFrame()
    frame.setObjectName(name)

    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 10, 14, 10)
    layout.setSpacing(7)

    return frame, layout


def make_theme_icon(mode: str, color: str) -> QIcon:
    """
    Draw vector-like icons locally.
    No external icon files or font symbols are required.
    """
    pixmap = QPixmap(48, 48)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(
        QPainter.RenderHint.Antialiasing
    )
    painter.scale(2, 2)

    pen = QPen(QColor(color))
    pen.setWidthF(1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)

    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    if mode == "Light":
        painter.drawEllipse(QRectF(8, 8, 8, 8))

        for angle in range(0, 360, 45):
            radians = math.radians(angle)

            start = QPointF(
                12 + math.cos(radians) * 7,
                12 + math.sin(radians) * 7,
            )
            end = QPointF(
                12 + math.cos(radians) * 9,
                12 + math.sin(radians) * 9,
            )

            painter.drawLine(start, end)

    elif mode == "Dark":
        outer = QPainterPath()
        outer.addEllipse(QRectF(4, 4, 16, 16))

        cutout = QPainterPath()
        cutout.addEllipse(QRectF(10, 1, 15, 15))

        crescent = outer.subtracted(cutout)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPath(crescent)

    else:
        painter.drawRoundedRect(
            QRectF(3, 4, 18, 13),
            2,
            2,
        )
        painter.drawLine(
            QPointF(12, 17),
            QPointF(12, 21),
        )
        painter.drawLine(
            QPointF(8, 21),
            QPointF(16, 21),
        )

    painter.end()

    return QIcon(pixmap)


class DeliveryNoteApp(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(
            "Delivery Note Converter"
        )

        self.settings = QSettings(
            "DeliveryNoteConverter",
            "Desktop",
        )

        self.selected_pdf = None
        self.delivery = None
        self.saved_path = None
        self.busy = False

        self.messages = Queue()
        self.shortcuts = []

        # Reuse the accent selected in the previous UI.
        self.accent = str(
            self.settings.value(
                "accent",
                "#5265E8",
            )
        )

        if not QColor(self.accent).isValid():
            self.accent = "#5265E8"

        self.theme_mode = str(
            self.settings.value(
                "theme",
                "System",
            )
        )

        if self.theme_mode not in (
            "Light",
            "Dark",
            "System",
        ):
            self.theme_mode = "System"

        self.configure_window_size()
        self.build_ui()
        self.connect_shortcuts()

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(140)
        self.search_timer.timeout.connect(
            self.filter_rows
        )

        self.search.textChanged.connect(
            self.schedule_search
        )

        app = QApplication.instance()

        app.styleHints().colorSchemeChanged.connect(
            self.system_theme_changed
        )

        self.apply_appearance()
        self.refresh_controls()

        self.poll_timer = QTimer(self)
        self.poll_timer.timeout.connect(
            self.poll_results
        )
        self.poll_timer.start(100)

    def configure_window_size(self):
        self.setMinimumSize(900, 560)

        screen = QApplication.primaryScreen()

        if screen is None:
            self.resize(1100, 680)
            return

        available = screen.availableGeometry()

        self.resize(
            max(
                900,
                min(1200, available.width() - 40),
            ),
            max(
                560,
                min(760, available.height() - 50),
            ),
        )

    def build_ui(self):
        root = QWidget()
        root.setObjectName("Root")
        self.setCentralWidget(root)

        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 12, 18, 12)
        layout.setSpacing(10)

        self.build_header(layout)
        self.build_source_panel(layout)
        self.build_metrics(layout)
        self.build_preview(layout)
        self.build_message_panel(layout)
        self.build_footer(layout)

    def build_header(self, layout):
        header = QHBoxLayout()
        header.setSpacing(12)

        brand = make_label("DN", "BrandMark")
        brand.setFixedSize(40, 40)
        brand.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )
        header.addWidget(brand)

        title_group = QVBoxLayout()
        title_group.setSpacing(1)

        title_group.addWidget(
            make_label(
                "Delivery Note Converter",
                "Title",
            )
        )
        title_group.addWidget(
            make_label(
                "Document operations  /  PDF to Excel",
                "Muted",
            )
        )

        header.addLayout(title_group, 1)

        self.state_badge = make_label(
            "Ready to begin",
            "Badge",
        )
        header.addWidget(self.state_badge)
        header.addSpacing(6)

        self.theme_group = QButtonGroup(self)
        self.theme_group.setExclusive(True)

        self.theme_buttons = {}

        for mode, description in (
            ("Light", "Light appearance"),
            ("Dark", "Dark appearance"),
            ("System", "Follow system appearance"),
        ):
            theme_button = QPushButton()
            theme_button.setObjectName(
                "ThemeButton"
            )
            theme_button.setFixedSize(36, 34)
            theme_button.setIconSize(QSize(20, 20))
            theme_button.setCheckable(True)
            theme_button.setChecked(
                mode == self.theme_mode
            )
            theme_button.setToolTip(description)
            theme_button.setAccessibleName(
                description
            )
            theme_button.setCursor(
                Qt.CursorShape.PointingHandCursor
            )

            theme_button.clicked.connect(
                lambda checked=False, selected=mode:
                    self.set_theme(selected)
            )

            self.theme_group.addButton(
                theme_button
            )
            self.theme_buttons[mode] = (
                theme_button
            )

            header.addWidget(theme_button)

        layout.addLayout(header)

    def build_source_panel(self, layout):
        source, source_layout = make_card("Hero")

        source_top = QHBoxLayout()
        source_top.setSpacing(10)

        source_top.addWidget(
            make_label(
                "SOURCE PDF",
                "Eyebrow",
            )
        )

        self.filename = make_label(
            "Choose a delivery note to begin",
            "FileName",
        )
        self.filename.setMinimumWidth(0)
        self.filename.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )

        source_top.addWidget(
            self.filename,
            1,
        )

        self.file_meta = make_label(
            "",
            "Muted",
        )
        source_top.addWidget(self.file_meta)

        self.select_button = make_button(
            "Choose PDF",
            self.select_pdf,
        )
        self.process_button = make_button(
            "Generate preview",
            self.generate_preview,
            primary=True,
        )

        source_top.addWidget(
            self.select_button
        )
        source_top.addWidget(
            self.process_button
        )

        source_layout.addLayout(source_top)

        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setFixedHeight(30)
        self.file_path.setPlaceholderText(
            "Select a PDF from your computer"
        )
        source_layout.addWidget(self.file_path)

        self.progress = QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(4)
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        source_layout.addWidget(self.progress)

        layout.addWidget(source)

    def build_metrics(self, layout):
        metrics = QGridLayout()
        metrics.setSpacing(10)

        self.metric_labels = []

        titles = (
            "DELIVERY NUMBER",
            "PACKING LISTS",
            "CARTON ROWS",
            "TOTAL MTS/BOX",
        )

        for index, title in enumerate(titles):
            metric, metric_layout = make_card()
            metric_layout.setContentsMargins(
                14, 8, 14, 8
            )
            metric_layout.setSpacing(2)

            metric_layout.addWidget(
                make_label(
                    title,
                    "Eyebrow",
                )
            )

            value = make_label(
                "—",
                "Metric",
            )
            value.setMinimumWidth(0)
            value.setSizePolicy(
                QSizePolicy.Policy.Ignored,
                QSizePolicy.Policy.Preferred,
            )
            value.setTextInteractionFlags(
                Qt.TextInteractionFlag.TextSelectableByMouse
            )

            metric_layout.addWidget(value)

            self.metric_labels.append(value)

            metrics.addWidget(
                metric,
                0,
                index,
            )
            metrics.setColumnStretch(
                index,
                1,
            )

        layout.addLayout(metrics)

    def build_preview(self, layout):
        preview, preview_layout = make_card()
        preview_layout.setSpacing(7)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        toolbar.addWidget(
            make_label(
                "Carton details",
                "Section",
            )
        )

        self.row_count = make_label(
            "No rows yet",
            "Muted",
        )
        toolbar.addWidget(self.row_count)
        toolbar.addStretch()

        self.search = QLineEdit()
        self.search.setPlaceholderText(
            "Search packing list, PO or carton..."
        )
        self.search.setClearButtonEnabled(True)
        self.search.setMinimumWidth(220)
        self.search.setMaximumWidth(320)
        self.search.setFixedHeight(32)

        toolbar.addWidget(self.search)

        preview_layout.addLayout(toolbar)

        self.preview_stack = QStackedWidget()
        self.preview_stack.setMinimumHeight(100)
        self.preview_stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        empty = QWidget()
        empty_layout = QVBoxLayout(empty)
        empty_layout.setContentsMargins(
            10, 6, 10, 6
        )
        empty_layout.setSpacing(5)

        empty_layout.addStretch()

        empty_title = make_label(
            "Your next export starts here.",
            "Section",
        )
        empty_title.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        empty_subtitle = make_label(
            "Choose a PDF and generate a preview.",
            "Muted",
        )
        empty_subtitle.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        empty_layout.addWidget(empty_title)
        empty_layout.addWidget(empty_subtitle)
        empty_layout.addStretch()

        self.preview_stack.addWidget(empty)

        self.table = QTableWidget(
            0,
            len(EXCEL_HEADERS),
        )
        self.table.setHorizontalHeaderLabels(
            EXCEL_HEADERS
        )
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)

        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(
            34
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setVerticalScrollMode(
            QAbstractItemView.ScrollMode.ScrollPerPixel
        )

        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self.table.horizontalHeader().setMinimumSectionSize(
            90
        )

        self.preview_stack.addWidget(self.table)

        no_results = make_label(
            "No matching rows. Clear the search "
            "to see all details.",
            "Muted",
        )
        no_results.setWordWrap(True)
        no_results.setAlignment(
            Qt.AlignmentFlag.AlignCenter
        )

        self.preview_stack.addWidget(no_results)

        preview_layout.addWidget(
            self.preview_stack,
            1,
        )

        preview_layout.addWidget(
            make_label(
                "Search filters the preview only. "
                "Export includes all validated rows.",
                "Muted",
            )
        )

        # Only this panel grows when the window grows.
        layout.addWidget(preview, 1)

    def build_message_panel(self, layout):
        message, message_layout = make_card()
        message_layout.setContentsMargins(
            14, 7, 14, 7
        )
        message_layout.setSpacing(3)

        message_top = QHBoxLayout()

        self.message_title = make_label(
            "Ready when you are",
            "Section",
        )
        message_top.addWidget(
            self.message_title,
            1,
        )

        copy_button = make_button(
            "Copy details",
            self.copy_details,
        )
        copy_button.setFixedHeight(28)

        message_top.addWidget(copy_button)
        message_layout.addLayout(message_top)

        self.details = QPlainTextEdit()
        self.details.setObjectName("Details")
        self.details.setReadOnly(True)
        self.details.setFixedHeight(42)
        self.details.setPlainText(
            "Select a PDF to start. Validation and "
            "export details will appear here."
        )

        message_layout.addWidget(self.details)

        layout.addWidget(message)

    def build_footer(self, layout):
        footer = QHBoxLayout()
        footer.setSpacing(8)

        self.status = make_label(
            "Waiting for a source document.",
            "Muted",
        )
        self.status.setMinimumWidth(0)
        self.status.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )

        footer.addWidget(self.status, 1)

        self.reset_button = make_button(
            "Reset",
            self.reset,
        )
        self.folder_button = make_button(
            "Open export folder",
            self.open_folder,
        )
        self.export_button = make_button(
            "Export Excel",
            self.save_excel,
            primary=True,
        )

        footer.addWidget(self.reset_button)
        footer.addWidget(self.folder_button)
        footer.addWidget(self.export_button)

        layout.addLayout(footer)

    def connect_shortcuts(self):
        actions = (
            ("Ctrl+O", self.select_pdf),
            ("Ctrl+F", self.focus_search),
            ("Ctrl+Shift+S", self.save_excel),
        )

        for key, callback in actions:
            shortcut = QShortcut(
                QKeySequence(key),
                self,
            )
            shortcut.activated.connect(callback)
            self.shortcuts.append(shortcut)

        self.select_button.setToolTip(
            "Choose PDF — Ctrl+O"
        )
        self.export_button.setToolTip(
            "Export all validated rows — Ctrl+Shift+S"
        )
        self.search.setToolTip(
            "Search preview — Ctrl+F"
        )

    def focus_search(self):
        if self.search.isEnabled():
            self.search.setFocus()

    def set_theme(self, mode):
        self.theme_mode = mode

        self.settings.setValue(
            "theme",
            mode,
        )

        self.apply_appearance()

    def system_theme_changed(self, *_):
        if self.theme_mode == "System":
            self.apply_appearance()

    def apply_appearance(self):
        app = QApplication.instance()
        mode = self.theme_mode

        if mode == "System":
            system_mode = (
                app.styleHints().colorScheme()
            )

            mode = (
                "Dark"
                if system_mode == Qt.ColorScheme.Dark
                else "Light"
            )

        colors = apply_theme(
            app,
            mode,
            self.accent,
        )

        selected_color = contrasting_text(
            QColor(self.accent)
        )

        for name, theme_button in self.theme_buttons.items():
            selected = name == self.theme_mode
            theme_button.setChecked(selected)

            icon_color = (
                selected_color
                if selected
                else colors["muted"]
            )

            theme_button.setIcon(
                make_theme_icon(
                    name,
                    icon_color,
                )
            )

        self.theme_buttons["System"].setToolTip(
            f"Follow system appearance — currently {mode}"
            if self.theme_mode == "System"
            else "Follow system appearance"
        )

    def show_message(
        self,
        title,
        details,
        level="info",
    ):
        self.message_title.setText(title)

        self.message_title.setObjectName(
            {
                "info": "Section",
                "success": "Success",
                "error": "Error",
            }.get(level, "Section")
        )

        style = self.message_title.style()
        style.unpolish(self.message_title)
        style.polish(self.message_title)

        self.details.setPlainText(details)

    def set_status(self, text):
        self.status.setText(text)
        self.status.setToolTip(text)

    def copy_details(self):
        QApplication.clipboard().setText(
            self.details.toPlainText()
        )

    def refresh_controls(self):
        available = not self.busy
        has_data = self.delivery is not None
        has_file = self.selected_pdf is not None

        self.select_button.setEnabled(available)
        self.select_button.setText(
            "Change PDF"
            if has_file
            else "Choose PDF"
        )

        self.process_button.setEnabled(
            available and has_file
        )

        self.export_button.setEnabled(
            available and has_data
        )

        self.search.setEnabled(
            available and has_data
        )

        self.reset_button.setEnabled(
            available and has_file
        )

        self.folder_button.setEnabled(
            available and self.saved_path is not None
        )

    def clear_results(self):
        self.search_timer.stop()

        self.delivery = None
        self.saved_path = None

        self.search.blockSignals(True)
        self.search.clear()
        self.search.blockSignals(False)

        self.table.setRowCount(0)
        self.row_count.setText("No rows yet")
        self.preview_stack.setCurrentIndex(0)

        for metric in self.metric_labels:
            metric.setText("—")
            metric.setToolTip("")

    def select_pdf(self):
        if self.busy:
            return

        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Choose delivery note",
            "",
            "PDF documents (*.pdf)",
        )

        if not filename:
            return

        path = Path(filename)

        try:
            size = path.stat().st_size

        except OSError as exc:
            QMessageBox.warning(
                self,
                "Cannot access file",
                str(exc),
            )
            return

        self.clear_results()
        self.selected_pdf = path

        self.filename.setText(path.name)
        self.filename.setToolTip(path.name)

        self.file_path.setText(str(path))
        self.file_path.setCursorPosition(0)

        size_text = (
            f"{size / 1048576:.2f} MB"
            if size >= 1048576
            else f"{size / 1024:.1f} KB"
        )

        self.file_meta.setText(size_text)

        self.state_badge.setText(
            "Document selected"
        )
        self.set_status(
            "Ready to generate a preview."
        )

        self.show_message(
            "Document selected",
            "Generate a preview to extract carton "
            "details and check the document totals.",
        )

        self.refresh_controls()

    def reset(self):
        if self.busy:
            return

        self.clear_results()
        self.selected_pdf = None

        self.filename.setText(
            "Choose a delivery note to begin"
        )
        self.filename.setToolTip("")

        self.file_meta.clear()
        self.file_path.clear()

        self.state_badge.setText(
            "Ready to begin"
        )

        self.set_status(
            "Waiting for a source document."
        )

        self.show_message(
            "Ready when you are",
            "Select a PDF to start a new conversion.",
        )

        self.refresh_controls()

    def start_job(
        self,
        action,
        function,
        *args,
    ):
        self.busy = True
        self.progress.setRange(0, 0)
        self.refresh_controls()

        def run():
            try:
                result = function(*args)

            except Exception as exc:
                self.messages.put(
                    (
                        action,
                        False,
                        f"{type(exc).__name__}: {exc}",
                    )
                )

            else:
                self.messages.put(
                    (
                        action,
                        True,
                        result,
                    )
                )

        Thread(
            target=run,
            daemon=True,
        ).start()

    @staticmethod
    def extract(path):
        pages = read_pdf(path)
        delivery = parse_delivery(pages)
        validate_delivery(delivery)

        return delivery

    def generate_preview(self):
        if self.busy or self.selected_pdf is None:
            return

        self.clear_results()

        self.state_badge.setText(
            "Processing"
        )

        self.set_status(
            "Reading and validating your PDF..."
        )

        self.show_message(
            "Checking your document",
            "Extracting Packing List details and "
            "comparing carton counts and quantities.",
        )

        self.start_job(
            "extract",
            self.extract,
            self.selected_pdf,
        )

    def populate_table(self):
        if self.delivery is None:
            return

        self.table.setUpdatesEnabled(False)

        try:
            self.table.setRowCount(
                len(self.delivery.records)
            )

            for row_index, record in enumerate(
                self.delivery.records
            ):
                values = (
                    record.delivery_no,
                    record.packing_list_no,
                    record.po_number,
                    record.rm_number,
                    record.carton_number,
                    f"{record.mts_per_box:,}",
                )

                for column, value in enumerate(values):
                    item = QTableWidgetItem(
                        str(value)
                    )

                    if column == 5:
                        item.setTextAlignment(
                            Qt.AlignmentFlag.AlignRight
                            | Qt.AlignmentFlag.AlignVCenter
                        )

                    self.table.setItem(
                        row_index,
                        column,
                        item,
                    )

        finally:
            self.table.setUpdatesEnabled(True)

        self.filter_rows()

    def schedule_search(self, *_):
        self.search_timer.start()

    def filter_rows(self):
        if self.delivery is None:
            return

        query = (
            self.search.text()
            .strip()
            .casefold()
        )

        visible = 0

        for index, record in enumerate(
            self.delivery.records
        ):
            searchable = " ".join(
                (
                    record.delivery_no,
                    record.packing_list_no,
                    record.po_number,
                    record.rm_number,
                    record.carton_number,
                    str(record.mts_per_box),
                    f"{record.mts_per_box:,}",
                )
            ).casefold()

            show = query in searchable

            self.table.setRowHidden(
                index,
                not show,
            )

            if show:
                visible += 1

        self.row_count.setText(
            f"{visible} of "
            f"{len(self.delivery.records)} rows"
        )

        self.preview_stack.setCurrentIndex(
            1 if visible else 2
        )

    def save_excel(self):
        if self.busy or self.delivery is None:
            return

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export Excel",
            f"DN-{self.delivery.delivery_no}.xlsx",
            "Excel workbook (*.xlsx)",
            options=(
                QFileDialog.Option.DontConfirmOverwrite
            ),
        )

        if not filename:
            return

        path = Path(filename)

        if not path.suffix:
            path = path.with_suffix(".xlsx")

        if path.suffix.lower() != ".xlsx":
            QMessageBox.warning(
                self,
                "Invalid filename",
                "Use the .xlsx file extension.",
            )
            return

        if path.exists():
            QMessageBox.warning(
                self,
                "Choose a new filename",
                "A file already exists at this location. "
                "Choose another name to keep the "
                "existing file.",
            )
            return

        self.state_badge.setText(
            "Exporting"
        )

        self.set_status(
            "Creating your Excel workbook..."
        )

        self.show_message(
            "Export in progress",
            f"Saving all "
            f"{len(self.delivery.records)} "
            "validated carton rows.",
        )

        self.start_job(
            "export",
            export_delivery,
            self.delivery,
            path,
        )

    def poll_results(self):
        try:
            action, success, result = (
                self.messages.get_nowait()
            )

        except Empty:
            return

        self.busy = False
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        if not success:
            self.state_badge.setText(
                "Needs attention"
            )

            self.set_status(
                "Review the details and try again."
            )

            self.show_message(
                "Processing failed"
                if action == "extract"
                else "Export failed",
                result,
                level="error",
            )

        elif action == "extract":
            self.delivery = result

            values = (
                result.delivery_no,
                str(len(result.packing_lists)),
                str(len(result.records)),
                f"{result.total_meters:,}",
            )

            for metric, value in zip(
                self.metric_labels,
                values,
                strict=True,
            ):
                metric.setText(value)
                metric.setToolTip(value)

            self.populate_table()

            self.state_badge.setText(
                "Ready to export"
            )

            self.set_status(
                "Review the preview, then export Excel."
            )

            self.show_message(
                "Validation passed",
                "Packing List totals and Delivery Note "
                "summary checks passed. Leading zeros "
                "will be preserved in the editable "
                "Excel workbook.",
                level="success",
            )

        else:
            self.saved_path = Path(result)

            self.state_badge.setText(
                "Export complete"
            )

            self.set_status(
                "Your Excel workbook is ready."
            )

            self.show_message(
                "Excel saved successfully",
                f"Saved to: {self.saved_path}\n"
                "Use Open export folder to find "
                "your workbook.",
                level="success",
            )

        self.refresh_controls()

    def open_folder(self):
        if self.saved_path is None:
            return

        folder = (
            self.saved_path.resolve().parent
        )

        opened = QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(folder))
        )

        if not opened:
            QMessageBox.information(
                self,
                "Export location",
                str(folder),
            )

    def closeEvent(self, event):
        if self.busy:
            QMessageBox.information(
                self,
                "Operation in progress",
                "Wait for processing to finish "
                "before closing.",
            )
            event.ignore()
            return

        self.settings.setValue(
            "theme",
            self.theme_mode,
        )
        self.settings.setValue(
            "accent",
            self.accent,
        )

        self.search_timer.stop()
        self.poll_timer.stop()

        event.accept()