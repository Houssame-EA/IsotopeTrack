# -*- coding: utf-8 -*-
"""Upper continental crust composition, used to compare element ratios with crustal values.

Values are mass fractions in ppm (ug/g) from Rudnick & Gao, "Composition of
the Continental Crust", Treatise on Geochemistry (2003, vol. 3, 1-64;
2nd edition 2014, vol. 4, 1-51), table of the upper continental crust.
Major elements given there as oxides (SiO2, Al2O3, FeO total, MnO, MgO,
CaO, Na2O, TiO2, K2O, P2O5) are converted to the element.
"""
from __future__ import annotations

REFERENCE = "Rudnick & Gao (2003, 2014), upper continental crust"
SHORT_REFERENCE = "Rudnick & Gao"

UCC_PPM = {
    'Si': 311300.0, 'Al': 81510.0, 'Fe': 39180.0, 'Mn': 774.5, 'Mg': 14960.0, 'Ca': 25660.0,
    'Na': 24260.0, 'Ti': 3836.0, 'K': 23240.0, 'P': 654.6, 'Li': 24.0, 'Be': 2.1,
    'B': 17.0, 'F': 557.0, 'S': 621.0, 'Cl': 370.0, 'Sc': 14.0, 'V': 97.0,
    'Cr': 92.0, 'Co': 17.3, 'Ni': 47.0, 'Cu': 28.0, 'Zn': 67.0, 'Ga': 17.5,
    'Ge': 1.4, 'As': 4.8, 'Se': 0.09, 'Br': 1.6, 'Rb': 84.0, 'Sr': 320.0,
    'Y': 21.0, 'Zr': 193.0, 'Nb': 12.0, 'Mo': 1.1, 'Ru': 0.00034, 'Pd': 0.00052,
    'Ag': 0.053, 'Cd': 0.09, 'In': 0.056, 'Sn': 2.1, 'Sb': 0.4, 'I': 1.4,
    'Cs': 4.9, 'Ba': 628.0, 'La': 31.0, 'Ce': 63.0, 'Pr': 7.1, 'Nd': 27.0,
    'Sm': 4.7, 'Eu': 1.0, 'Gd': 4.0, 'Tb': 0.7, 'Dy': 3.9, 'Ho': 0.83,
    'Er': 2.3, 'Tm': 0.3, 'Yb': 1.96, 'Lu': 0.31, 'Hf': 5.3, 'Ta': 0.9,
    'W': 1.9, 'Re': 0.000198, 'Os': 3.1e-05, 'Ir': 2.2e-05, 'Pt': 0.0005, 'Au': 0.0015,
    'Hg': 0.05, 'Tl': 0.9, 'Pb': 17.0, 'Bi': 0.16, 'Th': 10.5, 'U': 2.7,
}


def crust_ppm(symbol):
    """Upper-crust abundance of an element in ppm, or None when not tabulated.

    Args:
        symbol (str): Element symbol, e.g. ``'Ce'``.

    Returns:
        float | None: Mass fraction in ppm.
    """
    return UCC_PPM.get(symbol)


def crust_mass_ratio(a, b):
    """Mass ratio a/b in the upper crust, or None when either is not tabulated.

    Args:
        a (str): Numerator element symbol.
        b (str): Denominator element symbol.

    Returns:
        float | None: The ratio.
    """
    pa, pb = crust_ppm(a), crust_ppm(b)
    if not pa or not pb:
        return None
    return pa / pb
