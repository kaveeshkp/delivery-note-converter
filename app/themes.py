from PySide6.QtGui import QColor, QPalette


PALETTES = {
    "Light": {
        "bg": "#F4F6FA",
        "panel": "#FFFFFF",
        "text": "#172338",
        "muted": "#52647C",
        "border": "#D8E0EB",
        "soft": "#E9EEF5",
        "stripe": "#F7F9FC",
        "success": "#13764B",
        "error": "#B42318",
    },
    "Dark": {
        "bg": "#0C1220",
        "panel": "#141D2E",
        "text": "#EDF3FC",
        "muted": "#ACBDD3",
        "border": "#2B3950",
        "soft": "#202E43",
        "stripe": "#192437",
        "success": "#77DEAB",
        "error": "#FFA59D",
    },
}


def luminance(color: QColor) -> float:
    channels = []

    for value in (
        color.redF(),
        color.greenF(),
        color.blueF(),
    ):
        channels.append(
            value / 12.92
            if value <= 0.04045
            else ((value + 0.055) / 1.055) ** 2.4
        )

    return (
        0.2126 * channels[0]
        + 0.7152 * channels[1]
        + 0.0722 * channels[2]
    )


def contrasting_text(color: QColor) -> str:
    light = luminance(color)

    white_contrast = 1.05 / (light + 0.05)
    black_contrast = (light + 0.05) / 0.05

    return (
        "#FFFFFF"
        if white_contrast >= black_contrast
        else "#000000"
    )


def apply_theme(app, mode: str, accent: str):
    colors = PALETTES.get(mode, PALETTES["Light"])

    brand = QColor(accent)

    if not brand.isValid():
        brand = QColor("#5265E8")

    accent = brand.name()
    accent_text = contrasting_text(brand)

    hover = (
        brand.lighter(112)
        if mode == "Dark"
        else brand.darker(110)
    )

    hover_text = contrasting_text(hover)

    palette = QPalette()

    roles = {
        QPalette.ColorRole.Window: colors["bg"],
        QPalette.ColorRole.WindowText: colors["text"],
        QPalette.ColorRole.Base: colors["panel"],
        QPalette.ColorRole.AlternateBase: colors["stripe"],
        QPalette.ColorRole.Text: colors["text"],
        QPalette.ColorRole.Button: colors["panel"],
        QPalette.ColorRole.ButtonText: colors["text"],
        QPalette.ColorRole.Highlight: accent,
        QPalette.ColorRole.HighlightedText: accent_text,
        QPalette.ColorRole.ToolTipBase: colors["panel"],
        QPalette.ColorRole.ToolTipText: colors["text"],
        QPalette.ColorRole.PlaceholderText: colors["muted"],
    }

    for role, value in roles.items():
        palette.setColor(role, QColor(value))

    app.setPalette(palette)

    app.setStyleSheet(f"""
        QWidget {{
            color: {colors["text"]};
            font-family: "Segoe UI";
            font-size: 13px;
        }}

        QMainWindow, QWidget#Root {{
            background: {colors["bg"]};
        }}

        QFrame#Card {{
            background: {colors["panel"]};
            border: 1px solid {colors["border"]};
            border-radius: 12px;
        }}

        QFrame#Hero {{
            background: {colors["panel"]};
            border: 1px solid {colors["border"]};
            border-left: 4px solid {accent};
            border-radius: 12px;
        }}

        QLabel {{
            background: transparent;
            border: none;
        }}

        QLabel#Title {{
            font-size: 20px;
            font-weight: 700;
        }}

        QLabel#Section {{
            font-size: 15px;
            font-weight: 600;
        }}

        QLabel#Metric {{
            font-size: 22px;
            font-weight: 700;
        }}

        QLabel#FileName {{
            font-size: 13px;
            font-weight: 600;
        }}

        QLabel#Muted {{
            color: {colors["muted"]};
            font-size: 12px;
        }}

        QLabel#Eyebrow {{
            color: {colors["muted"]};
            font-size: 10px;
            font-weight: 600;
        }}

        QLabel#BrandMark {{
            background: {accent};
            color: {accent_text};
            border-radius: 10px;
            font-size: 17px;
            font-weight: 700;
        }}

        QLabel#Badge {{
            background: {colors["soft"]};
            color: {colors["text"]};
            border-radius: 9px;
            padding: 6px 10px;
            font-size: 12px;
            font-weight: 600;
        }}

        QLabel#Success {{
            color: {colors["success"]};
            font-size: 14px;
            font-weight: 600;
        }}

        QLabel#Error {{
            color: {colors["error"]};
            font-size: 14px;
            font-weight: 600;
        }}

        QPushButton {{
            background: {colors["panel"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            border-radius: 8px;
            padding: 7px 12px;
            font-weight: 600;
        }}

        QPushButton:hover {{
            background: {colors["soft"]};
        }}

        QPushButton#Primary {{
            background: {accent};
            color: {accent_text};
            border: 1px solid {accent};
        }}

        QPushButton#Primary:hover {{
            background: {hover.name()};
            color: {hover_text};
            border-color: {hover.name()};
        }}

        QPushButton:disabled,
        QPushButton#Primary:disabled {{
            background: {colors["soft"]};
            color: {colors["muted"]};
            border-color: {colors["border"]};
        }}

        QPushButton#ThemeButton {{
            padding: 0px;
            border-radius: 8px;
        }}

        QPushButton#ThemeButton:checked {{
            background: {accent};
            border: 1px solid {accent};
        }}

        QPushButton:focus {{
            border: 2px solid {accent};
        }}

        QLineEdit, QPlainTextEdit {{
            background: {colors["panel"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            border-radius: 7px;
            padding: 6px 9px;
            selection-background-color: {accent};
            selection-color: {accent_text};
        }}

        QLineEdit:focus {{
            border: 2px solid {accent};
        }}

        QLineEdit:disabled {{
            background: {colors["soft"]};
            color: {colors["muted"]};
        }}

        QPlainTextEdit#Details {{
            background: {colors["panel"]};
            border: none;
            padding: 0px;
            font-size: 12px;
        }}

        QTableWidget {{
            background: {colors["panel"]};
            alternate-background-color: {colors["stripe"]};
            color: {colors["text"]};
            border: none;
            selection-background-color: {accent};
            selection-color: {accent_text};
        }}

        QTableWidget::item {{
            padding: 5px;
            border: none;
        }}

        QTableWidget::item:selected {{
            background: {accent};
            color: {accent_text};
        }}

        QHeaderView::section {{
            background: {colors["soft"]};
            color: {colors["muted"]};
            border: none;
            padding: 8px;
            font-weight: 600;
        }}

        QProgressBar {{
            background: {colors["soft"]};
            border: none;
            border-radius: 2px;
        }}

        QProgressBar::chunk {{
            background: {accent};
            border-radius: 2px;
        }}

        QToolTip {{
            background: {colors["panel"]};
            color: {colors["text"]};
            border: 1px solid {colors["border"]};
            padding: 6px;
        }}
    """)

    return colors