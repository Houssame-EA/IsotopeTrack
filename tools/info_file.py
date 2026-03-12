"""File information display dialogs and menus for viewing method and run information."""
from PySide6.QtWidgets import (
    QMenu, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QWidget, QFrame, QPushButton, QSizePolicy, QSpacerItem, QGridLayout
)
from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QSize
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush, QPalette
import numpy as np


# ── Palette ───────────────────────────────────────────────────────────────────
CLR_BG          = "#f4f5f7"
CLR_SURFACE     = "#ffffff"
CLR_BORDER      = "#dde1e7"
CLR_HEADER_BG   = "#1c2b3a"
CLR_ACCENT      = "#2563eb"
CLR_TEXT        = "#111827"
CLR_TEXT_MUTED  = "#6b7280"
CLR_ROW_ALT     = "#f9fafb"
CLR_ENABLED     = "#16a34a"
CLR_DISABLED    = "#dc2626"
CLR_DIVIDER     = "#e5e7eb"


# ── Reusable components ───────────────────────────────────────────────────────

class Divider(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.HLine)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background: {CLR_DIVIDER}; border: none;")


class SectionHeader(QWidget):
    """Compact section title with accent bar on the left."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 16, 0)
        layout.setSpacing(10)

        bar = QFrame()
        bar.setFixedSize(3, 16)
        bar.setStyleSheet(f"background: {CLR_ACCENT}; border-radius: 2px;")

        label = QLabel(title.upper())
        label.setStyleSheet(f"""
            color: {CLR_ACCENT};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.8px;
        """)

        layout.addWidget(bar)
        layout.addWidget(label)
        layout.addStretch()

        self.setStyleSheet(f"background: {CLR_ROW_ALT};")


class ParamRow(QWidget):
    """Single label/value row with optional unit."""
    def __init__(self, label, value, unit="", alternate=False, parent=None):
        super().__init__(parent)

        bg = CLR_ROW_ALT if alternate else CLR_SURFACE
        self.setStyleSheet(f"background: {bg};")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 18, 0)
        layout.setSpacing(8)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 13px; background: transparent;")

        val = QLabel(str(value))
        val.setStyleSheet(f"color: {CLR_TEXT}; font-size: 13px; font-weight: 600; background: transparent;")
        val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(lbl, 1)
        layout.addWidget(val)

        if unit:
            u = QLabel(unit)
            u.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 12px; background: transparent; min-width: 28px;")
            layout.addWidget(u)

        layout.addStretch(0)


class StatusRow(QWidget):
    """Label/value row where value is coloured by enabled/disabled state."""
    def __init__(self, label, enabled, alternate=False, parent=None):
        super().__init__(parent)
        bg = CLR_ROW_ALT if alternate else CLR_SURFACE
        self.setStyleSheet(f"background: {bg};")
        self.setFixedHeight(36)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 18, 0)

        lbl = QLabel(label)
        lbl.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 13px; background: transparent;")

        dot = QLabel("●")
        color = CLR_ENABLED if enabled else CLR_DISABLED
        dot.setStyleSheet(f"color: {color}; font-size: 10px; background: transparent;")

        val = QLabel("Enabled" if enabled else "Disabled")
        val.setStyleSheet(f"color: {color}; font-size: 13px; font-weight: 600; background: transparent;")

        layout.addWidget(lbl, 1)
        layout.addWidget(dot)
        layout.addWidget(val)


class Card(QWidget):
    """White card with border and title, containing stacked rows."""
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            Card {{
                background: {CLR_SURFACE};
                border: 1px solid {CLR_BORDER};
                border-radius: 8px;
            }}
        """)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        header = SectionHeader(title)
        self._layout.addWidget(header)
        self._row_count = 0

    def add_row(self, label, value, unit=""):
        alternate = (self._row_count % 2 == 1)
        row = ParamRow(label, value, unit, alternate)
        self._layout.addWidget(row)
        self._row_count += 1

    def add_status_row(self, label, enabled):
        alternate = (self._row_count % 2 == 1)
        row = StatusRow(label, enabled, alternate)
        self._layout.addWidget(row)
        self._row_count += 1

    def add_divider(self, sub_title):
        """Add a visual sub-group divider with a label."""
        spacer = QWidget()
        spacer.setFixedHeight(1)
        spacer.setStyleSheet(f"background: {CLR_DIVIDER};")
        self._layout.addWidget(spacer)

        sub = QLabel(sub_title)
        sub.setContentsMargins(18, 8, 18, 4)
        sub.setStyleSheet(f"""
            color: {CLR_TEXT_MUTED};
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 0.5px;
            text-transform: uppercase;
            background: {CLR_SURFACE};
        """)
        self._layout.addWidget(sub)
        self._row_count = 0  # reset alternation after sub-divider


class SummaryBar(QWidget):
    """Dark top bar showing key stats at a glance."""
    def __init__(self, stats, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self.setStyleSheet(f"""
            background: {CLR_HEADER_BG};
            border-bottom: 1px solid #253649;
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(32, 0, 32, 0)
        layout.setSpacing(0)

        for i, (label, value, unit) in enumerate(stats):
            if i > 0:
                div = QFrame()
                div.setFixedSize(1, 36)
                div.setStyleSheet("background: #2e4260;")
                layout.addWidget(div)

            item = QWidget()
            item.setStyleSheet("background: transparent;")
            item_l = QVBoxLayout(item)
            item_l.setContentsMargins(24, 0, 24, 0)
            item_l.setSpacing(2)
            item_l.setAlignment(Qt.AlignCenter)

            val_row = QHBoxLayout()
            val_row.setSpacing(4)
            val_row.setAlignment(Qt.AlignCenter)

            v = QLabel(str(value))
            v.setStyleSheet("color: #ffffff; font-size: 20px; font-weight: 700; background: transparent;")
            val_row.addWidget(v)

            if unit:
                u = QLabel(unit)
                u.setStyleSheet(f"color: #7a99b8; font-size: 13px; background: transparent; padding-top: 5px;")
                val_row.addWidget(u)

            l = QLabel(label)
            l.setStyleSheet(f"color: #7a99b8; font-size: 10px; letter-spacing: 0.6px; background: transparent;")
            l.setAlignment(Qt.AlignCenter)

            item_l.addLayout(val_row)
            item_l.addWidget(l)

            layout.addWidget(item, 1)


# ── Dialog ────────────────────────────────────────────────────────────────────

class FileInfoDialog(QDialog):
    """Dialog for displaying detailed file information."""

    def __init__(self, sample_name, run_info, method_info, time_array, masses, parent=None):
        super().__init__(parent)
        self.sample_name = sample_name
        self.run_info = run_info
        self.method_info = method_info
        self.time_array = time_array
        self.masses = masses

        self.setWindowTitle(f"Method Information — {sample_name}")
        self.setMinimumSize(780, 680)
        self.resize(820, 720)
        self.setup_ui()

    def setup_ui(self):
        self.setStyleSheet(f"""
            QDialog {{
                background: {CLR_BG};
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                border: none;
                background: #e5e7eb;
                width: 7px;
                border-radius: 4px;
                margin: 2px;
            }}
            QScrollBar::handle:vertical {{
                background: #9ca3af;
                border-radius: 4px;
                min-height: 20px;
            }}
            QScrollBar::handle:vertical:hover {{
                background: #6b7280;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
            QPushButton {{
                background: {CLR_ACCENT};
                color: white;
                border: none;
                padding: 7px 20px;
                border-radius: 5px;
                font-size: 13px;
                font-weight: 500;
            }}
            QPushButton:hover {{ background: #1d4ed8; }}
            QPushButton:pressed {{ background: #1e40af; }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Title bar
        title_bar = QWidget()
        title_bar.setFixedHeight(52)
        title_bar.setStyleSheet(f"""
            background: {CLR_HEADER_BG};
            border-bottom: 1px solid #253649;
        """)
        tb_layout = QHBoxLayout(title_bar)
        tb_layout.setContentsMargins(24, 0, 24, 0)

        title_lbl = QLabel("Method & Acquisition Information")
        title_lbl.setStyleSheet("color: #f9fafb; font-size: 15px; font-weight: 600; background: transparent;")

        sample_lbl = QLabel(self.sample_name)
        sample_lbl.setStyleSheet(f"color: #7a99b8; font-size: 13px; background: transparent;")
        sample_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        tb_layout.addWidget(title_lbl)
        tb_layout.addStretch()
        tb_layout.addWidget(sample_lbl)
        root.addWidget(title_bar)

        # ── Summary bar (populated later)
        self._summary_placeholder = None

        # ── Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("background: transparent; border: none;")

        self._content = QWidget()
        self._content.setStyleSheet(f"background: {CLR_BG};")
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(20, 20, 20, 20)
        self._content_layout.setSpacing(12)
        self._content_layout.addStretch()

        scroll.setWidget(self._content)
        root.addWidget(scroll, 1)

        # ── Footer
        footer = QWidget()
        footer.setFixedHeight(52)
        footer.setStyleSheet(f"background: {CLR_SURFACE}; border-top: 1px solid {CLR_BORDER};")
        footer_l = QHBoxLayout(footer)
        footer_l.setContentsMargins(20, 0, 20, 0)
        footer_l.addStretch()
        close_btn = QPushButton("Close")
        close_btn.setFixedWidth(80)
        close_btn.clicked.connect(self.accept)
        footer_l.addWidget(close_btn)
        root.addWidget(footer)

        self._build_content()

    def _insert_card(self, card):
        """Insert card before the trailing stretch."""
        count = self._content_layout.count()
        self._content_layout.insertWidget(count - 1, card)

    def _build_content(self):
        if not self.run_info:
            msg = QLabel("No run information was stored with this sample.")
            msg.setAlignment(Qt.AlignCenter)
            msg.setStyleSheet(f"color: {CLR_TEXT_MUTED}; font-size: 14px; padding: 60px;")
            self._insert_card(msg)
            return

        try:
            seg       = self.run_info["SegmentInfo"][0]
            acqtime   = seg["AcquisitionPeriodNs"] * 1e-9
            accum     = self.run_info["NumAccumulations1"] * self.run_info["NumAccumulations2"]
            dwell     = acqtime * accum
            n_points  = len(self.time_array) if self.time_array is not None else 0
            total_s   = float(self.time_array[-1] - self.time_array[0]) if n_points > 1 else 0

            # Summary bar injected before scroll
            summary_bar = SummaryBar([
                ("Data Points",    f"{n_points:,}",         ""),
                ("Duration",       f"{total_s/60:.1f}",     "min"),
                ("Dwell Time",     f"{dwell*1000:.3f}",     "ms"),
                ("Sampling Rate",  f"{1/dwell:.1f}",        "Hz"),
            ])
            self.layout().insertWidget(2, summary_bar)

            # Method configuration
            if self.method_info:
                self._build_method_card(self.method_info["Segments"][0])

            # Acquisition parameters
            acq_card = Card("Acquisition Parameters")
            acq_card.add_row("Dwell Time",        f"{dwell*1000:.3f}", "ms")
            acq_card.add_row("Total Duration",    f"{total_s:.2f} s  /  {total_s/60:.1f} min")
            acq_card.add_row("Data Points",       f"{n_points:,}")
            acq_card.add_row("Sampling Rate",     f"{1/dwell:.1f}", "Hz")
            self._insert_card(acq_card)

            # Mass configuration
            if self.masses is not None and len(self.masses) > 0:
                mass_card = Card("Mass Analysis")
                mass_card.add_row("Mass Range",    f"{min(self.masses):.3f} – {max(self.masses):.3f}", "amu")
                mass_card.add_row("Mass Points",   f"{len(self.masses)}")
                mass_card.add_row("Range / Points",f"{(max(self.masses)-min(self.masses))/len(self.masses):.4f}", "amu/point")
                mass_card.add_row("Median Step",   f"{np.median(np.diff(self.masses)):.4f}", "amu")
                self._insert_card(mass_card)

            # Run information
            self._build_run_info_card()

        except Exception as e:
            err = QLabel(f"Error loading information:\n{e}")
            err.setAlignment(Qt.AlignCenter)
            err.setStyleSheet(f"color: {CLR_DISABLED}; font-size: 13px; padding: 40px;")
            err.setWordWrap(True)
            self._insert_card(err)

    def _build_method_card(self, segment):
        hex_c  = segment["HexapoleConfig"]
        quad_c = segment["QuadrupoleConfig"]
        ab_c   = segment["AutoBlankingConfig"]

        card = Card("Method Configuration")

        card.add_divider("Data Acquisition")
        card.add_row("Mass Range",        f"{segment['StartMass']:.1f} – {segment['EndMass']:.1f}", "amu")
        card.add_row("Acquisition Count", f"{segment['AcquisitionCount']:,}")
        card.add_row("Acquisition Period",f"{segment['AcquisitionPeriod']}", "ns")
        card.add_row("Tick Frequency",    f"{self.method_info['InstrumentTickFrequencyNs']}", "ns")

        card.add_divider("Hexapole")
        card.add_row("Cell Entrance",     f"{hex_c['CellEntranceVoltage']:.1f}", "V")
        card.add_row("Entrance Aperture", f"{hex_c['EntranceApertureVoltage']:.1f}", "V")
        card.add_row("Exit Aperture",     f"{hex_c['ExitApertureVoltage']:.1f}", "V")
        card.add_row("Cell Exit",         f"{hex_c['CellExitVoltage']:.1f}", "V")
        card.add_row("RF Reference",      f"{hex_c['RfReference']:.1f}")

        card.add_divider("Quadrupole")
        card.add_row("Bias Voltage",      f"{quad_c['BiasVoltage']:.1f}", "V")
        card.add_row("RF Reference",      f"{quad_c['RfReference']:.1f}")
        card.add_row("DC Reference",      f"{quad_c['DcReference']:.1f}")

        card.add_divider("Autoblanking")
        card.add_status_row("Status",     ab_c["IsEnabled"])
        card.add_row("Blanker",           f"{ab_c['BlankerToUse']}")
        card.add_row("Combine Threshold", f"{ab_c['CombineThreshold']}")
        card.add_row("Filter Threshold",  f"{ab_c['FilterThreshold']}")
        card.add_row("Min Blanking Width",f"{ab_c['MinBlankingWidth']}")

        skip = segment.get("SkipMassRanges", [])
        if skip:
            card.add_divider("Skip Mass Ranges")
            for i, r in enumerate(skip):
                card.add_row(f"Range {i+1}", f"{r['StartMass']:.1f} – {r['EndMass']:.1f}", "amu")

        self._insert_card(card)

    def _build_run_info_card(self):
        segs = self.run_info["SegmentInfo"]
        card = Card("Run Information")
        card.add_row("Segments",               f"{len(segs)}")
        card.add_row("Base Acquisition Period",f"{segs[0]['AcquisitionPeriodNs']/1000:.2f}", "µs")
        card.add_row("Accumulations 1",        f"{self.run_info['NumAccumulations1']}")
        card.add_row("Accumulations 2",        f"{self.run_info['NumAccumulations2']}")

        if len(segs) > 1:
            card.add_divider("Segment Detail")
            for s in segs:
                card.add_row(f"  Seg {s['Num']} — Trigger Delay",
                             f"{s['AcquisitionTriggerDelayNs']/1000:.2f}", "µs")
                card.add_row(f"  Seg {s['Num']} — Acq. Period",
                             f"{s['AcquisitionPeriodNs']/1000:.2f}", "µs")

        self._insert_card(card)


# ── Menu helper ───────────────────────────────────────────────────────────────

class FileInfoMenu:
    @staticmethod
    def create_menu(sample_name, run_info, method_info, time_array, masses, parent=None):
        menu = QMenu(parent)
        action = menu.addAction("Show Method Information")
        action.triggered.connect(lambda: FileInfoMenu.show_file_info(
            sample_name, run_info, method_info, time_array, masses, parent
        ))
        return menu

    @staticmethod
    def show_file_info(sample_name, run_info, method_info, time_array, masses, parent=None):
        dialog = FileInfoDialog(sample_name, run_info, method_info, time_array, masses, parent)
        dialog.exec()