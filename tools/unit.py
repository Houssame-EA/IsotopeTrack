"""Units dialog (visual): one choice of units for the whole app.

The unit definitions, ``ExportUnits`` value object, formatters, persistence
and the app-wide ``units`` object live in ``utils/unit.py``. This module only
builds the dialog.
"""
import logging

from utils.unit import (
    ExportUnits, units,
    MASS_UNITS, MOLES_UNITS, DIAMETER_UNITS, CONCENTRATION_UNITS,
)

_itk_log = logging.getLogger("IsotopeTrack.tools.unit")


# --------------------------------------------------------------------------- #
# Advanced Options dialog
# --------------------------------------------------------------------------- #

def show_advanced_dialog(parent, current: ExportUnits) -> ExportUnits | None:
    """Open the Units dialog and return the updated ExportUnits, or None if
    the user cancels. On OK the choice is applied to the whole app.
    """
    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox,
        QComboBox, QSpinBox, QLabel, QDialogButtonBox, QPushButton,
    )
    from PySide6.QtCore import Qt
    from tools.theme import theme, dialog_qss

    dlg = QDialog(parent)
    dlg.setWindowTitle("Units")
    dlg.setObjectName("advancedExportDialog")
    dlg.setMinimumWidth(440)

    def _apply(*_):
        dlg.setStyleSheet(dialog_qss(theme.palette))
    _apply()
    theme.themeChanged.connect(_apply)
    dlg.destroyed.connect(lambda *_: theme.themeChanged.disconnect(_apply))

    root = QVBoxLayout(dlg)
    root.setContentsMargins(16, 16, 16, 16)
    root.setSpacing(14)

    intro = QLabel(
        "Choose the units shown everywhere: results, figures, Insights, "
        "cluster, AI and exported files.\n"
        "Data is still computed and saved in fg, fmol, nm and ppb, so only "
        "what you see changes."
    )
    intro.setWordWrap(True)
    intro.setStyleSheet(f"color: {theme.palette.text_secondary};")
    root.addWidget(intro)

    # ---- Units group ------------------------------------------------------
    units_group = QGroupBox("Units")
    units_form = QFormLayout()
    units_form.setContentsMargins(12, 10, 12, 12)
    units_form.setSpacing(10)
    units_form.setLabelAlignment(Qt.AlignLeft)

    mass_cb = QComboBox()
    mass_cb.addItems(MASS_UNITS.keys())
    mass_cb.setCurrentText(current.mass_unit)

    moles_cb = QComboBox()
    moles_cb.addItems(MOLES_UNITS.keys())
    moles_cb.setCurrentText(current.moles_unit)

    diameter_cb = QComboBox()
    diameter_cb.addItems(DIAMETER_UNITS.keys())
    diameter_cb.setCurrentText(current.diameter_unit)

    conc_cb = QComboBox()
    conc_cb.addItems(CONCENTRATION_UNITS.keys())
    conc_cb.setCurrentText(current.concentration_unit)

    units_form.addRow("Mass:", mass_cb)
    units_form.addRow("Moles:", moles_cb)
    units_form.addRow("Diameter:", diameter_cb)
    units_form.addRow("Mass concentration:", conc_cb)
    units_group.setLayout(units_form)
    root.addWidget(units_group)

    # ---- Number format group ---------------------------------------------
    format_group = QGroupBox("Number Format")
    format_form = QFormLayout()
    format_form.setContentsMargins(12, 10, 12, 12)
    format_form.setSpacing(10)

    format_cb = QComboBox()
    format_cb.addItem("Decimal (e.g. 0.00012)",  "decimal")
    format_cb.addItem("Scientific (e.g. 1.2e-4)", "scientific")
    format_cb.setCurrentIndex(0 if current.number_format == "decimal" else 1)

    mass_dec = QSpinBox();  mass_dec.setRange(0, 12);  mass_dec.setValue(current.mass_decimals)
    moles_dec = QSpinBox(); moles_dec.setRange(0, 12); moles_dec.setValue(current.moles_decimals)
    dia_dec = QSpinBox();   dia_dec.setRange(0, 12);   dia_dec.setValue(current.diameter_decimals)
    conc_dec = QSpinBox();  conc_dec.setRange(0, 12);  conc_dec.setValue(current.concentration_decimals)

    format_form.addRow("Format:", format_cb)
    format_form.addRow("Mass decimals:", mass_dec)
    format_form.addRow("Moles decimals:", moles_dec)
    format_form.addRow("Diameter decimals:", dia_dec)
    format_form.addRow("Concentration decimals:", conc_dec)
    format_group.setLayout(format_form)
    root.addWidget(format_group)

    # ---- Preview ----------------------------------------------------------
    preview_label = QLabel()
    preview_label.setStyleSheet(
        f"color: {theme.palette.text_secondary}; "
        f"background: {theme.palette.bg_tertiary}; "
        f"border: 1px solid {theme.palette.border}; "
        f"border-radius: 4px; padding: 8px;"
    )
    preview_label.setTextFormat(Qt.PlainText)
    root.addWidget(preview_label)

    def _chosen():
        return ExportUnits(
            mass_unit=mass_cb.currentText(),
            moles_unit=moles_cb.currentText(),
            diameter_unit=diameter_cb.currentText(),
            number_format=format_cb.currentData(),
            mass_decimals=mass_dec.value(),
            moles_decimals=moles_dec.value(),
            diameter_decimals=dia_dec.value(),
            concentration_unit=conc_cb.currentText(),
            concentration_decimals=conc_dec.value(),
        )

    def _update_preview(*_):
        sample_mass_fg = 1234.5
        sample_moles_fmol = 0.678
        sample_diameter_nm = 45.67
        sample_ppb = 1.234
        u = _chosen()
        preview_label.setText(
            "Preview:\n"
            f"  Mass      → {u.fmt_mass(sample_mass_fg)} {u.mass_label}\n"
            f"  Moles     → {u.fmt_moles(sample_moles_fmol)} {u.moles_label}\n"
            f"  Diameter  → {u.fmt_diameter(sample_diameter_nm)} {u.diameter_label}\n"
            f"  Conc.     → {u.fmt_concentration(sample_ppb)} {u.concentration_label}"
        )

    for w in (mass_cb, moles_cb, diameter_cb, conc_cb, format_cb):
        w.currentIndexChanged.connect(_update_preview)
    for w in (mass_dec, moles_dec, dia_dec, conc_dec):
        w.valueChanged.connect(_update_preview)
    _update_preview()

    # ---- Buttons ----------------------------------------------------------
    btn_row = QHBoxLayout()
    reset_btn = QPushButton("Reset to defaults")
    btn_row.addWidget(reset_btn)
    btn_row.addStretch()

    buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
    buttons.button(QDialogButtonBox.Ok).setDefault(True)
    buttons.accepted.connect(dlg.accept)
    buttons.rejected.connect(dlg.reject)
    btn_row.addWidget(buttons)
    root.addLayout(btn_row)

    def _reset():
        defaults = ExportUnits()
        mass_cb.setCurrentText(defaults.mass_unit)
        moles_cb.setCurrentText(defaults.moles_unit)
        diameter_cb.setCurrentText(defaults.diameter_unit)
        format_cb.setCurrentIndex(0)
        mass_dec.setValue(defaults.mass_decimals)
        moles_dec.setValue(defaults.moles_decimals)
        dia_dec.setValue(defaults.diameter_decimals)
        conc_cb.setCurrentText(defaults.concentration_unit)
        conc_dec.setValue(defaults.concentration_decimals)
    reset_btn.clicked.connect(_reset)

    if dlg.exec() != QDialog.Accepted:
        return None

    updated = _chosen()
    units.set(updated)
    return updated


def show_units_dialog(parent) -> ExportUnits | None:
    """Open the Units dialog on the app's current units."""
    return show_advanced_dialog(parent, units.current)
