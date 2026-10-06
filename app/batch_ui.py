from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QProgressBar,
    QVBoxLayout,
)

from app.batch_exporter import export_batch
from app.batch_service import process_batch
from app.ui import (
    DeliveryNoteApp,
    make_button,
    make_card,
    make_label,
)


class BatchDeliveryNoteApp(DeliveryNoteApp):
    def __init__(self):
        self.selected_paths = []

        super().__init__()

        self.setWindowTitle(
            "Delivery Note Converter — Batch Workspace"
        )

        self.show_message(
            "Ready for multiple documents",
            "Choose one or more PDFs. Each document will be "
            "validated before its rows are combined into "
            "one Excel worksheet.",
        )

    def build_source_panel(self, layout):
        source, source_layout = make_card("Hero")

        source_top = QHBoxLayout()
        source_top.setSpacing(10)

        source_top.addWidget(
            make_label(
                "SOURCE DOCUMENTS",
                "Eyebrow",
            )
        )

        self.filename = make_label(
            "No PDFs selected",
            "FileName",
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
            "Choose PDFs",
            self.select_pdf,
        )

        self.files_button = make_button(
            "Files (0)",
            self.manage_files,
        )

        self.process_button = make_button(
            "Generate preview",
            self.generate_preview,
            primary=True,
        )

        source_top.addWidget(self.select_button)
        source_top.addWidget(self.files_button)
        source_top.addWidget(self.process_button)

        source_layout.addLayout(source_top)

        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        self.file_path.setFixedHeight(30)
        self.file_path.setPlaceholderText(
            "Choose multiple PDFs using Ctrl or Shift"
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

        for index, title in enumerate(
            (
                "SELECTED PDFS",
                "DELIVERIES",
                "CARTON ROWS",
                "TOTAL MTS/BOX",
            )
        ):
            metric, metric_layout = make_card()

            metric_layout.setContentsMargins(
                14, 8, 14, 8
            )
            metric_layout.setSpacing(2)

            metric_layout.addWidget(
                make_label(title, "Eyebrow")
            )

            value = make_label("—", "Metric")
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

    def refresh_controls(self):
        available = not self.busy
        has_files = bool(self.selected_paths)
        has_data = self.delivery is not None

        self.select_button.setEnabled(available)
        self.select_button.setText(
            "Add PDFs"
            if has_files
            else "Choose PDFs"
        )

        self.files_button.setEnabled(
            available and has_files
        )
        self.files_button.setText(
            f"Files ({len(self.selected_paths)})"
        )

        self.process_button.setEnabled(
            available and has_files
        )
        self.export_button.setEnabled(
            available and has_data
        )
        self.search.setEnabled(
            available and has_data
        )
        self.reset_button.setEnabled(
            available and has_files
        )
        self.folder_button.setEnabled(
            available and self.saved_path is not None
        )

    def clear_results(self):
        super().clear_results()

        self.metric_labels[0].setText(
            str(len(self.selected_paths))
        )

    def update_source_display(self):
        count = len(self.selected_paths)

        if not count:
            self.filename.setText(
                "No PDFs selected"
            )
            self.file_meta.clear()
            self.file_path.clear()
            self.file_path.setToolTip("")
            return

        self.filename.setText(
            f"{count} PDF document"
            + ("" if count == 1 else "s")
        )

        try:
            total_size = sum(
                path.stat().st_size
                for path in self.selected_paths
            )

            size_text = (
                f"{total_size / 1048576:.2f} MB"
                if total_size >= 1048576
                else f"{total_size / 1024:.1f} KB"
            )

            self.file_meta.setText(size_text)

        except OSError:
            self.file_meta.setText(
                "File access needs checking"
            )

        names = "; ".join(
            path.name
            for path in self.selected_paths
        )

        self.file_path.setText(names)
        self.file_path.setCursorPosition(0)

        self.file_path.setToolTip(
            "\n".join(
                str(path)
                for path in self.selected_paths
            )
        )

    def select_pdf(self):
        if self.busy:
            return

        filenames, _ = QFileDialog.getOpenFileNames(
            self,
            "Choose delivery-note PDFs",
            "",
            "PDF documents (*.pdf)",
        )

        if not filenames:
            return

        known = set(self.selected_paths)
        added = 0

        for filename in filenames:
            path = Path(filename).resolve()

            if path in known:
                continue

            self.selected_paths.append(path)
            known.add(path)
            added += 1

        if not added:
            self.set_status(
                "These files are already selected."
            )
            return

        self.clear_results()
        self.update_source_display()

        self.state_badge.setText(
            "Documents selected"
        )

        self.set_status(
            f"{len(self.selected_paths)} PDFs ready to process."
        )

        self.show_message(
            "Documents selected",
            "Generate a preview to process all selected PDFs.\n"
            "Use Files to review or remove documents. "
            "One failed document will block the combined export.",
        )

        self.refresh_controls()

    def manage_files(self):
        if self.busy or not self.selected_paths:
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(
            "Selected PDF documents"
        )
        dialog.resize(720, 400)

        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.setContentsMargins(
            18, 18, 18, 18
        )
        dialog_layout.setSpacing(12)

        description = make_label(
            "Select files to remove, then apply your changes.",
            "Muted",
        )
        description.setWordWrap(True)
        dialog_layout.addWidget(description)

        file_list = QListWidget()
        file_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        for path in self.selected_paths:
            item = QListWidgetItem(
                f"{path.name}\n{path.parent}"
            )
            item.setData(
                Qt.ItemDataRole.UserRole,
                str(path),
            )
            item.setToolTip(str(path))
            file_list.addItem(item)

        dialog_layout.addWidget(file_list, 1)

        actions = QHBoxLayout()

        def remove_selected():
            for item in file_list.selectedItems():
                file_list.takeItem(
                    file_list.row(item)
                )

        remove_button = make_button(
            "Remove selected",
            remove_selected,
        )
        cancel_button = make_button(
            "Cancel",
            dialog.reject,
        )
        apply_button = make_button(
            "Apply changes",
            dialog.accept,
            primary=True,
        )

        actions.addWidget(remove_button)
        actions.addStretch()
        actions.addWidget(cancel_button)
        actions.addWidget(apply_button)

        dialog_layout.addLayout(actions)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        updated = [
            Path(
                file_list.item(index).data(
                    Qt.ItemDataRole.UserRole
                )
            )
            for index in range(file_list.count())
        ]

        if updated == self.selected_paths:
            return

        self.selected_paths = updated
        self.clear_results()
        self.update_source_display()

        self.state_badge.setText(
            "Documents selected"
            if updated
            else "Ready to begin"
        )

        self.set_status(
            "Selection changed. Generate a new preview."
            if updated
            else "Choose PDFs to begin."
        )

        self.show_message(
            "File selection updated",
            "The previous preview was cleared. "
            "Generate a new preview for the current selection."
            if updated
            else "No PDFs are selected.",
        )

        self.refresh_controls()

    def reset(self):
        if self.busy:
            return

        self.selected_paths.clear()
        self.selected_pdf = None

        self.clear_results()
        self.update_source_display()

        self.state_badge.setText(
            "Ready to begin"
        )
        self.set_status(
            "Choose PDFs to begin."
        )

        self.show_message(
            "Ready for multiple documents",
            "Choose one or more PDFs to create "
            "a combined Excel workbook.",
        )

        self.refresh_controls()

    def extract_selected(self, paths):
        def progress(message):
            self.messages.put(
                ("progress", True, message)
            )

        return process_batch(
            paths,
            progress=progress,
        )

    def generate_preview(self):
        if self.busy or not self.selected_paths:
            return

        paths = tuple(self.selected_paths)

        self.clear_results()

        self.state_badge.setText(
            "Processing batch"
        )
        self.set_status(
            f"Processing {len(paths)} selected PDFs..."
        )

        self.show_message(
            "Checking selected documents",
            "Each PDF is validated separately. "
            "Duplicate files and overlapping carton "
            "records will also be checked.",
        )

        self.start_job(
            "extract",
            self.extract_selected,
            paths,
        )

    def poll_results(self):
        from queue import Empty

        try:
            action, success, result = (
                self.messages.get_nowait()
            )

        except Empty:
            return

        if action == "progress":
            self.set_status(result)
            return

        self.busy = False
        self.progress.setRange(0, 1)
        self.progress.setValue(0)

        if not success:
            self.state_badge.setText(
                "Needs attention"
            )

            self.set_status(
                "Review the affected files and try again."
                if action == "extract"
                else "Export failed. The preview is still available."
            )

            self.show_message(
                "Batch processing failed"
                if action == "extract"
                else "Export failed",
                result,
                level="error",
            )

        elif action == "extract":
            # The inherited table methods use .records,
            # which BatchData also provides.
            self.delivery = result

            values = (
                str(result.file_count),
                str(result.delivery_count),
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
                "All selected PDFs passed. "
                "Review the combined rows."
            )

            self.show_message(
                "Batch validation passed",
                f"{result.file_count} PDFs, "
                f"{result.delivery_count} deliveries, "
                f"{result.packing_list_count} Packing Lists "
                f"and {len(result.records)} carton rows.\n"
                "Export will include all validated rows "
                "in one filterable worksheet.",
                level="success",
            )

        else:
            self.saved_path = Path(result)

            self.state_badge.setText(
                "Export complete"
            )
            self.set_status(
                "Your combined Excel workbook is ready."
            )

            self.show_message(
                "Combined Excel saved",
                f"Saved to: {self.saved_path}\n"
                "Use the Excel header filters to select "
                "a delivery, Packing List, PO or carton.",
                level="success",
            )

        self.refresh_controls()

    def save_excel(self):
        if self.busy or self.delivery is None:
            return

        batch = self.delivery

        default_name = (
            f"DN-{batch.delivery_numbers[0]}.xlsx"
            if batch.delivery_count == 1
            else "Combined-Delivery-Notes.xlsx"
        )

        filename, _ = QFileDialog.getSaveFileName(
            self,
            "Export combined Excel",
            default_name,
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
                "This file already exists. "
                "Choose another filename.",
            )
            return

        self.state_badge.setText(
            "Exporting"
        )
        self.set_status(
            "Creating the combined Excel workbook..."
        )

        self.show_message(
            "Export in progress",
            f"Saving {len(batch.records)} carton rows "
            f"from {batch.file_count} PDFs.",
        )

        self.start_job(
            "export",
            export_batch,
            batch,
            path,
        )