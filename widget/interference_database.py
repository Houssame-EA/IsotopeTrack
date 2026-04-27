"""
ICP-MS Interference Database for spICP-ToF-MS

Comprehensive database of known spectral interferences including:
- Isobaric (same nominal mass from different elements)
- Polyatomic / Argide (ArO+, ArAr+, ArN+, ArCl+, etc.)
- Oxide (MO+, MOH+)
- Chloride (MCl+)
- Doubly-charged (M2+)
- Nitride / Hydride adducts

Used for:
1. Per-particle interference diagnosis
2. Smart isotope auto-selection (scoring function)
3. Visual warnings in periodic table and plots

References:
    May & Wiedmeyer, Atomic Spectroscopy 19(5), 150-155 (1998)
    Thomas, Practical Guide to ICP-MS, 3rd Ed. (2013)
    Balcaen et al., Anal. Chim. Acta 894, 7-19 (2015)
"""

import numpy as np
from typing import Dict, List, Optional, Tuple, Set


# ---------------------------------------------------------------------------
# Plasma species — always present regardless of sample composition
# ---------------------------------------------------------------------------
PLASMA_SPECIES = frozenset({'Ar', 'O', 'N', 'H', 'C'})


# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------

INTERFERENCE_DB: Dict[int, list] = {
    24: [
        {'species': '¹²C₂⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['C', 'C'], 'exact_mass': 24.000, 'plasma_based': True},
    ],
    27: [
        {'species': '¹²C¹⁵N⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['C', 'N'], 'exact_mass': 27.003, 'plasma_based': True},
    ],
    28: [
        {'species': '¹⁴N₂⁺', 'type': 'polyatomic', 'severity': 'critical',
         'components': ['N', 'N'], 'exact_mass': 28.006, 'plasma_based': True},
        {'species': '¹²C¹⁶O⁺', 'type': 'polyatomic', 'severity': 'major',
         'components': ['C', 'O'], 'exact_mass': 27.995, 'plasma_based': True},
    ],
    29: [
        {'species': '¹⁴N¹⁵N⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['N', 'N'], 'exact_mass': 29.003, 'plasma_based': True},
        {'species': '¹³C¹⁶O⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['C', 'O'], 'exact_mass': 28.998, 'plasma_based': True},
    ],
    30: [
        {'species': '¹⁴N¹⁶O⁺', 'type': 'polyatomic', 'severity': 'critical',
         'components': ['N', 'O'], 'exact_mass': 29.998, 'plasma_based': True},
    ],
    31: [
        {'species': '¹⁵N¹⁶O⁺', 'type': 'polyatomic', 'severity': 'major',
         'components': ['N', 'O'], 'exact_mass': 30.995, 'plasma_based': True},
        {'species': '¹⁴N¹⁶O¹H⁺', 'type': 'polyatomic', 'severity': 'major',
         'components': ['N', 'O', 'H'], 'exact_mass': 31.006, 'plasma_based': True},
    ],
    32: [
        {'species': '¹⁶O₂⁺', 'type': 'polyatomic', 'severity': 'critical',
         'components': ['O', 'O'], 'exact_mass': 31.990, 'plasma_based': True},
    ],
    33: [
        {'species': '¹⁶O¹⁷O⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['O', 'O'], 'exact_mass': 32.994, 'plasma_based': True},
        {'species': '¹⁶O¹⁴N¹H₂⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['O', 'N', 'H'], 'exact_mass': 33.014, 'plasma_based': True},
    ],
    34: [
        {'species': '¹⁶O¹⁸O⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['O', 'O'], 'exact_mass': 33.994, 'plasma_based': True},
    ],
    39: [
        {'species': '³⁸Ar¹H⁺', 'type': 'argide', 'severity': 'major',
         'components': ['Ar', 'H'], 'exact_mass': 38.971, 'plasma_based': True},
    ],
    40: [
        {'species': '⁴⁰Ar⁺', 'type': 'isobaric', 'severity': 'critical',
         'components': ['Ar'], 'exact_mass': 39.962, 'plasma_based': True,
         'note': 'Dominant Ar plasma interference on 40Ca and 40K'},
    ],
    41: [
        {'species': '⁴⁰Ar¹H⁺', 'type': 'argide', 'severity': 'critical',
         'components': ['Ar', 'H'], 'exact_mass': 40.971, 'plasma_based': True},
    ],
    44: [
        {'species': '¹²C¹⁶O₂⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['C', 'O'], 'exact_mass': 43.990, 'plasma_based': True},
        {'species': '²⁸Si¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Si'], 'exact_mass': 43.972, 'plasma_based': False},
        {'species': '⁸⁸Sr²⁺', 'type': 'doubly_charged', 'severity': 'minor',
         'components': ['Sr'], 'exact_mass': 43.953, 'plasma_based': False},
    ],
    46: [
        {'species': '³⁰Si¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Si'], 'exact_mass': 45.969, 'plasma_based': False},
    ],
    47: [
        {'species': '³¹P¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['P'], 'exact_mass': 46.969, 'plasma_based': False},
        {'species': '³⁰Si¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'minor',
         'components': ['Si'], 'exact_mass': 46.977, 'plasma_based': False},
    ],
    48: [
        {'species': '³²S¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['S'], 'exact_mass': 47.967, 'plasma_based': False},
        {'species': '³⁶Ar¹²C⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['Ar', 'C'], 'exact_mass': 47.967, 'plasma_based': True},
    ],
    50: [
        {'species': '³⁴S¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['S'], 'exact_mass': 49.964, 'plasma_based': False},
        {'species': '³⁶Ar¹⁴N⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Ar', 'N'], 'exact_mass': 49.971, 'plasma_based': True},
    ],
    51: [
        {'species': '³⁵Cl¹⁶O⁺', 'type': 'chloride', 'severity': 'critical',
         'components': ['Cl'], 'exact_mass': 50.964, 'plasma_based': False,
         'note': 'Major ClO+ interference on 51V'},
        {'species': '³⁴S¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'minor',
         'components': ['S'], 'exact_mass': 50.975, 'plasma_based': False},
    ],
    52: [
        {'species': '⁴⁰Ar¹²C⁺', 'type': 'argide', 'severity': 'major',
         'components': ['Ar', 'C'], 'exact_mass': 51.962, 'plasma_based': True},
        {'species': '³⁵Cl¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'major',
         'components': ['Cl'], 'exact_mass': 51.972, 'plasma_based': False},
        {'species': '³⁶S¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['S'], 'exact_mass': 51.963, 'plasma_based': False},
    ],
    53: [
        {'species': '³⁷Cl¹⁶O⁺', 'type': 'chloride', 'severity': 'major',
         'components': ['Cl'], 'exact_mass': 52.961, 'plasma_based': False},
        {'species': '⁴⁰Ar¹³C⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Ar', 'C'], 'exact_mass': 52.965, 'plasma_based': True},
    ],
    54: [
        {'species': '⁴⁰Ar¹⁴N⁺', 'type': 'argide', 'severity': 'critical',
         'components': ['Ar', 'N'], 'exact_mass': 53.966, 'plasma_based': True,
         'note': 'ArN+ on 54Fe and 54Cr'},
        {'species': '³⁷Cl¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'minor',
         'components': ['Cl'], 'exact_mass': 53.969, 'plasma_based': False},
    ],
    55: [
        {'species': '⁴⁰Ar¹⁵N⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Ar', 'N'], 'exact_mass': 54.963, 'plasma_based': True},
        {'species': '⁴⁰Ar¹⁴N¹H⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Ar', 'N', 'H'], 'exact_mass': 54.974, 'plasma_based': True},
        {'species': '³⁹K¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['K'], 'exact_mass': 54.960, 'plasma_based': False},
    ],
    56: [
        {'species': '⁴⁰Ar¹⁶O⁺', 'type': 'argide', 'severity': 'critical',
         'components': ['Ar', 'O'], 'exact_mass': 55.957, 'plasma_based': True,
         'note': 'Major ArO+ interference on 56Fe'},
        {'species': '⁴⁰Ca¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Ca'], 'exact_mass': 55.958, 'plasma_based': False,
         'note': 'CaO+ from Ca-bearing particles'},
    ],
    57: [
        {'species': '⁴⁰Ar¹⁶O¹H⁺', 'type': 'argide', 'severity': 'major',
         'components': ['Ar', 'O', 'H'], 'exact_mass': 56.965, 'plasma_based': True},
        {'species': '⁴⁰Ca¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'minor',
         'components': ['Ca'], 'exact_mass': 56.966, 'plasma_based': False},
    ],
    58: [
        {'species': '⁴²Ca¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ca'], 'exact_mass': 57.954, 'plasma_based': False},
        {'species': '⁴⁰Ar¹⁸O⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Ar', 'O'], 'exact_mass': 57.956, 'plasma_based': True},
        {'species': '²³Na³⁵Cl⁺', 'type': 'chloride', 'severity': 'minor',
         'components': ['Na', 'Cl'], 'exact_mass': 57.958, 'plasma_based': False},
    ],
    59: [
        {'species': '⁴³Ca¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ca'], 'exact_mass': 58.954, 'plasma_based': False},
        {'species': '⁴²Ca¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'minor',
         'components': ['Ca'], 'exact_mass': 58.962, 'plasma_based': False},
    ],
    60: [
        {'species': '⁴⁴Ca¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Ca'], 'exact_mass': 59.951, 'plasma_based': False,
         'note': 'CaO+ on 60Ni — use 44Ca to check'},
        {'species': '²³Na³⁷Cl⁺', 'type': 'chloride', 'severity': 'minor',
         'components': ['Na', 'Cl'], 'exact_mass': 59.956, 'plasma_based': False},
    ],
    61: [
        {'species': '⁴⁴Ca¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'minor',
         'components': ['Ca'], 'exact_mass': 60.959, 'plasma_based': False},
    ],
    63: [
        {'species': '⁴⁰Ar²³Na⁺', 'type': 'argide', 'severity': 'major',
         'components': ['Na'], 'exact_mass': 62.952, 'plasma_based': False},
        {'species': '⁴⁷Ti¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ti'], 'exact_mass': 62.947, 'plasma_based': False},
    ],
    64: [
        {'species': '⁴⁸Ti¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ti'], 'exact_mass': 63.944, 'plasma_based': False},
        {'species': '³²S₂⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['S', 'S'], 'exact_mass': 63.944, 'plasma_based': False},
        {'species': '⁴⁸Ca¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ca'], 'exact_mass': 63.948, 'plasma_based': False},
    ],
    65: [
        {'species': '⁴⁹Ti¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ti'], 'exact_mass': 64.944, 'plasma_based': False},
        {'species': '⁴⁰Ar²⁵Mg⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Mg'], 'exact_mass': 64.948, 'plasma_based': False},
    ],
    66: [
        {'species': '⁵⁰Ti¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ti'], 'exact_mass': 65.940, 'plasma_based': False},
        {'species': '⁵⁰Cr¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Cr'], 'exact_mass': 65.942, 'plasma_based': False},
        {'species': '³⁴S¹⁶O₂⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['S'], 'exact_mass': 65.964, 'plasma_based': False},
    ],
    70: [
        {'species': '⁵⁴Fe¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Fe'], 'exact_mass': 69.935, 'plasma_based': False},
        {'species': '³⁵Cl₂⁺', 'type': 'chloride', 'severity': 'minor',
         'components': ['Cl', 'Cl'], 'exact_mass': 69.938, 'plasma_based': False},
        {'species': '⁴⁰Ar³⁰Si⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Si'], 'exact_mass': 69.936, 'plasma_based': False},
    ],
    71: [
        {'species': '⁵⁵Mn¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Mn'], 'exact_mass': 70.934, 'plasma_based': False},
        {'species': '⁴⁰Ar³¹P⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['P'], 'exact_mass': 70.936, 'plasma_based': False},
    ],
    72: [
        {'species': '⁵⁶Fe¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Fe'], 'exact_mass': 71.931, 'plasma_based': False},
        {'species': '⁴⁰Ar³²S⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['S'], 'exact_mass': 71.934, 'plasma_based': False},
    ],
    73: [
        {'species': '⁵⁷Fe¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Fe'], 'exact_mass': 72.931, 'plasma_based': False},
    ],
    74: [
        {'species': '⁵⁸Fe¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Fe'], 'exact_mass': 73.929, 'plasma_based': False},
        {'species': '⁵⁸Ni¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ni'], 'exact_mass': 73.931, 'plasma_based': False},
        {'species': '⁴⁰Ar³⁴S⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['S'], 'exact_mass': 73.930, 'plasma_based': False},
    ],
    75: [
        {'species': '⁴⁰Ar³⁵Cl⁺', 'type': 'argide', 'severity': 'critical',
         'components': ['Cl'], 'exact_mass': 74.931, 'plasma_based': False,
         'note': 'ArCl+ is the major interference on 75As'},
        {'species': '⁵⁹Co¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Co'], 'exact_mass': 74.929, 'plasma_based': False},
        {'species': '⁴³Ca¹⁶O₂⁺', 'type': 'polyatomic', 'severity': 'minor',
         'components': ['Ca'], 'exact_mass': 74.950, 'plasma_based': False},
        {'species': '¹⁵⁰Nd²⁺', 'type': 'doubly_charged', 'severity': 'minor',
         'components': ['Nd'], 'exact_mass': 74.960, 'plasma_based': False},
        {'species': '¹⁵⁰Sm²⁺', 'type': 'doubly_charged', 'severity': 'minor',
         'components': ['Sm'], 'exact_mass': 74.959, 'plasma_based': False},
    ],
    76: [
        {'species': '⁶⁰Ni¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ni'], 'exact_mass': 75.927, 'plasma_based': False},
        {'species': '⁴⁰Ar³⁶S⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['S'], 'exact_mass': 75.929, 'plasma_based': False},
        {'species': '¹⁵²Sm²⁺', 'type': 'doubly_charged', 'severity': 'minor',
         'components': ['Sm'], 'exact_mass': 75.960, 'plasma_based': False},
    ],
    77: [
        {'species': '⁴⁰Ar³⁷Cl⁺', 'type': 'argide', 'severity': 'major',
         'components': ['Cl'], 'exact_mass': 76.928, 'plasma_based': False},
        {'species': '⁶¹Ni¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ni'], 'exact_mass': 76.927, 'plasma_based': False},
    ],
    78: [
        {'species': '⁴⁰Ar³⁸Ar⁺', 'type': 'argide', 'severity': 'major',
         'components': ['Ar', 'Ar'], 'exact_mass': 77.925, 'plasma_based': True},
        {'species': '⁶²Ni¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ni'], 'exact_mass': 77.924, 'plasma_based': False},
    ],
    80: [
        {'species': '⁴⁰Ar₂⁺', 'type': 'argide', 'severity': 'critical',
         'components': ['Ar', 'Ar'], 'exact_mass': 79.924, 'plasma_based': True,
         'note': 'Ar2+ is the dominant interference on 80Se'},
    ],
    82: [
        {'species': '⁴⁰Ar⁴²Ca⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Ca'], 'exact_mass': 81.921, 'plasma_based': False},
        {'species': '⁸²Kr⁺', 'type': 'isobaric', 'severity': 'minor',
         'components': ['Kr'], 'exact_mass': 81.913, 'plasma_based': True,
         'note': 'Kr trace in Ar gas'},
    ],
    85: [
        {'species': '⁶⁹Ga¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ga'], 'exact_mass': 84.921, 'plasma_based': False},
    ],
    86: [
        {'species': '⁷⁰Ge¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ge'], 'exact_mass': 85.920, 'plasma_based': False},
    ],
    88: [
        {'species': '⁷²Ge¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ge'], 'exact_mass': 87.918, 'plasma_based': False},
    ],
    90: [
        {'species': '⁷⁴Ge¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ge'], 'exact_mass': 89.917, 'plasma_based': False},
    ],
    95: [
        {'species': '⁷⁹Br¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Br'], 'exact_mass': 94.914, 'plasma_based': False},
        {'species': '⁴⁰Ar⁵⁵Mn⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Mn'], 'exact_mass': 94.900, 'plasma_based': False},
    ],
    96: [
        {'species': '⁸⁰Se¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Se'], 'exact_mass': 95.912, 'plasma_based': False},
    ],
    98: [
        {'species': '⁸²Se¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Se'], 'exact_mass': 97.913, 'plasma_based': False},
        {'species': '⁴⁰Ar⁵⁸Ni⁺', 'type': 'argide', 'severity': 'minor',
         'components': ['Ni'], 'exact_mass': 97.897, 'plasma_based': False},
    ],
    103: [
        {'species': '⁸⁷Sr¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sr'], 'exact_mass': 102.905, 'plasma_based': False},
        {'species': '⁸⁷Rb¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Rb'], 'exact_mass': 102.907, 'plasma_based': False},
        {'species': '²⁰⁶Pb²⁺', 'type': 'doubly_charged', 'severity': 'minor',
         'components': ['Pb'], 'exact_mass': 102.987, 'plasma_based': False},
    ],
    104: [
        {'species': '⁸⁸Sr¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Sr'], 'exact_mass': 103.902, 'plasma_based': False},
        {'species': '²⁰⁸Pb²⁺', 'type': 'doubly_charged', 'severity': 'minor',
         'components': ['Pb'], 'exact_mass': 103.988, 'plasma_based': False},
    ],
    105: [
        {'species': '⁸⁹Y¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Y'], 'exact_mass': 104.902, 'plasma_based': False},
    ],
    107: [
        {'species': '⁹¹Zr¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Zr'], 'exact_mass': 106.901, 'plasma_based': False,
         'note': 'ZrO+ interference — check for Zr in particle'},
    ],
    108: [
        {'species': '⁹²Zr¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Zr'], 'exact_mass': 107.901, 'plasma_based': False},
        {'species': '⁹²Mo¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Mo'], 'exact_mass': 107.903, 'plasma_based': False},
    ],
    109: [
        {'species': '⁹³Nb¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Nb'], 'exact_mass': 108.902, 'plasma_based': False},
        {'species': '⁹²Zr¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'minor',
         'components': ['Zr'], 'exact_mass': 108.909, 'plasma_based': False},
    ],
    111: [
        {'species': '⁹⁵Mo¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Mo'], 'exact_mass': 110.902, 'plasma_based': False},
    ],
    114: [
        {'species': '⁹⁸Mo¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Mo'], 'exact_mass': 113.901, 'plasma_based': False},
    ],
    115: [
        {'species': '⁹⁹Ru¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ru'], 'exact_mass': 114.902, 'plasma_based': False},
    ],
    118: [
        {'species': '¹⁰²Ru¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ru'], 'exact_mass': 117.900, 'plasma_based': False},
    ],
    135: [
        {'species': '¹¹⁹Sn¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sn'], 'exact_mass': 134.899, 'plasma_based': False},
    ],
    137: [
        {'species': '¹²¹Sb¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sb'], 'exact_mass': 136.900, 'plasma_based': False},
    ],
    138: [
        {'species': '¹²²Sn¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sn'], 'exact_mass': 137.899, 'plasma_based': False},
    ],
    139: [
        {'species': '¹²³Sb¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sb'], 'exact_mass': 138.900, 'plasma_based': False},
    ],
    140: [
        {'species': '¹²⁴Sn¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sn'], 'exact_mass': 139.901, 'plasma_based': False},
    ],
    151: [
        {'species': '¹³⁵Ba¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Ba'], 'exact_mass': 150.902, 'plasma_based': False},
    ],
    152: [
        {'species': '¹³⁶Ba¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Ba'], 'exact_mass': 151.901, 'plasma_based': False},
        {'species': '¹³⁶Ce¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ce'], 'exact_mass': 151.903, 'plasma_based': False},
    ],
    153: [
        {'species': '¹³⁷Ba¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Ba'], 'exact_mass': 152.902, 'plasma_based': False,
         'note': 'BaO+ on 153Eu'},
    ],
    154: [
        {'species': '¹³⁸Ba¹⁶O⁺', 'type': 'oxide', 'severity': 'critical',
         'components': ['Ba'], 'exact_mass': 153.901, 'plasma_based': False,
         'note': 'BaO+ on 154Sm and 154Gd'},
        {'species': '¹³⁸Ce¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ce'], 'exact_mass': 153.902, 'plasma_based': False},
        {'species': '¹³⁸La¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['La'], 'exact_mass': 153.903, 'plasma_based': False},
    ],
    155: [
        {'species': '¹³⁹La¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['La'], 'exact_mass': 154.902, 'plasma_based': False,
         'note': 'LaO+ on 155Gd'},
    ],
    156: [
        {'species': '¹⁴⁰Ce¹⁶O⁺', 'type': 'oxide', 'severity': 'critical',
         'components': ['Ce'], 'exact_mass': 155.901, 'plasma_based': False,
         'note': 'CeO+ on 156Gd and 156Dy — very common REE interference'},
    ],
    157: [
        {'species': '¹⁴¹Pr¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Pr'], 'exact_mass': 156.904, 'plasma_based': False,
         'note': 'PrO+ on 157Gd'},
        {'species': '¹⁴⁰Ce¹⁶O¹H⁺', 'type': 'hydroxide', 'severity': 'minor',
         'components': ['Ce'], 'exact_mass': 156.909, 'plasma_based': False},
    ],
    158: [
        {'species': '¹⁴²Nd¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Nd'], 'exact_mass': 157.904, 'plasma_based': False},
        {'species': '¹⁴²Ce¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ce'], 'exact_mass': 157.905, 'plasma_based': False},
    ],
    159: [
        {'species': '¹⁴³Nd¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Nd'], 'exact_mass': 158.906, 'plasma_based': False},
    ],
    160: [
        {'species': '¹⁴⁴Nd¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Nd'], 'exact_mass': 159.906, 'plasma_based': False},
        {'species': '¹⁴⁴Sm¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sm'], 'exact_mass': 159.908, 'plasma_based': False},
    ],
    161: [
        {'species': '¹⁴⁵Nd¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Nd'], 'exact_mass': 160.909, 'plasma_based': False},
    ],
    162: [
        {'species': '¹⁴⁶Nd¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Nd'], 'exact_mass': 161.911, 'plasma_based': False},
    ],
    163: [
        {'species': '¹⁴⁷Sm¹⁶O⁺', 'type': 'oxide', 'severity': 'major',
         'components': ['Sm'], 'exact_mass': 162.911, 'plasma_based': False},
    ],
    165: [
        {'species': '¹⁴⁹Sm¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sm'], 'exact_mass': 164.913, 'plasma_based': False},
    ],
    166: [
        {'species': '¹⁵⁰Nd¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Nd'], 'exact_mass': 165.917, 'plasma_based': False},
        {'species': '¹⁵⁰Sm¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Sm'], 'exact_mass': 165.913, 'plasma_based': False},
    ],
    197: [
        {'species': '¹⁸¹Ta¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Ta'], 'exact_mass': 196.944, 'plasma_based': False},
    ],
    202: [
        {'species': '¹⁸⁶W¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['W'], 'exact_mass': 201.950, 'plasma_based': False},
    ],
    208: [
        {'species': '¹⁹²Os¹⁶O⁺', 'type': 'oxide', 'severity': 'minor',
         'components': ['Os'], 'exact_mass': 207.957, 'plasma_based': False},
    ],
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_interferences_for_mass(nominal_mass: int) -> list:
    """
    Get all known interferences for a given nominal mass.

    Args:
        nominal_mass: Integer nominal mass (e.g. 56 for 56Fe)

    Returns:
        List of interference dicts, empty if none known
    """
    return INTERFERENCE_DB.get(nominal_mass, [])


def get_particle_relevant_interferences(nominal_mass: int,
                                         elements_in_particle: Set[str]) -> list:
    """
    Get interferences that are plausible for a specific particle based on
    which elements were co-detected.

    Plasma-based interferences (ArO+, Ar2+, etc.) are always included.
    Non-plasma interferences are only included if ALL required non-plasma
    components are present in the particle.

    Args:
        nominal_mass: Integer nominal mass being evaluated
        elements_in_particle: Set of element symbols detected in this particle

    Returns:
        List of plausible interference dicts
    """
    all_interferences = get_interferences_for_mass(nominal_mass)
    plausible = []

    for interf in all_interferences:
        if interf.get('plasma_based', False):
            plausible.append(interf)
        else:
            non_plasma_components = [c for c in interf['components']
                                     if c not in PLASMA_SPECIES]
            if all(comp in elements_in_particle for comp in non_plasma_components):
                plausible.append(interf)

    return plausible


def get_worst_severity(interferences: list) -> str:
    """
    Get the worst (most severe) interference severity from a list.

    Args:
        interferences: List of interference dicts

    Returns:
        'critical', 'major', 'minor', or 'none'
    """
    severity_order = {'critical': 3, 'major': 2, 'minor': 1}
    worst = 0
    for interf in interferences:
        sev = severity_order.get(interf.get('severity', 'minor'), 0)
        if sev > worst:
            worst = sev

    reverse_map = {3: 'critical', 2: 'major', 1: 'minor', 0: 'none'}
    return reverse_map[worst]


def has_any_interference(nominal_mass: int) -> bool:
    """
    Quick check if a nominal mass has any known interferences.

    Args:
        nominal_mass: Integer nominal mass

    Returns:
        True if interferences are known
    """
    return nominal_mass in INTERFERENCE_DB and len(INTERFERENCE_DB[nominal_mass]) > 0


# ---------------------------------------------------------------------------
# Smart isotope scoring (replaces hardcoded PREFERRED_ISOTOPES)
# ---------------------------------------------------------------------------

def score_isotope(mass: float, abundance: float,
                  interferences: list,
                  abundance_weight: float = 1.0,
                  interference_weight: float = 50.0,
                  min_abundance: float = 0.5) -> float:
    """
    Score an isotope for auto-selection. Higher score = better choice.

    The score balances abundance (we want high signal) against interference
    risk (we want clean measurements).

    Score = abundance - (severity_penalty * interference_weight)

    For isotopes below min_abundance, a heavy penalty is applied to avoid
    selecting isotopes with too little signal.

    Args:
        mass: Exact isotope mass
        abundance: Natural abundance as percentage (0-100)
        interferences: List of interference dicts for this mass
        abundance_weight: Weight for abundance term (default 1.0)
        interference_weight: Penalty weight per interference (default 50.0)
        min_abundance: Minimum abundance % to consider (default 0.5)

    Returns:
        Float score (higher is better)
    """
    score = abundance * abundance_weight

    if abundance < min_abundance:
        score -= 200.0

    severity_penalties = {'critical': 3.0, 'major': 2.0, 'minor': 0.5}
    for interf in interferences:
        penalty = severity_penalties.get(interf.get('severity', 'minor'), 0.5)
        if interf.get('plasma_based', False):
            penalty *= 1.5
        score -= penalty * interference_weight

    return score


def get_best_isotope(element_data: dict,
                     available_masses: list = None,
                     abundance_weight: float = 1.0,
                     interference_weight: float = 50.0,
                     min_abundance: float = 0.5) -> Optional[dict]:
    """
    Select the best isotope for an element based on abundance and
    interference scoring.

    Args:
        element_data: Element dict from PeriodicTableWidget containing
            'symbol', 'isotopes' list
        available_masses: Optional list of masses available in the data.
            If provided, only isotopes matching available masses are
            considered (tolerance 0.5 Da).
        abundance_weight: Weight for abundance in scoring
        interference_weight: Weight for interference penalty
        min_abundance: Minimum abundance to consider

    Returns:
        Best isotope dict {'mass', 'abundance', 'label', 'score',
                          'interferences'} or None if no isotopes available
    """
    symbol = element_data.get('symbol', '')
    isotopes = element_data.get('isotopes', [])

    candidates = []

    for iso in isotopes:
        if not isinstance(iso, dict):
            continue

        mass = iso.get('mass', 0)
        abundance = iso.get('abundance', 0)
        label = iso.get('label', f'{round(mass)}{symbol}')

        if abundance <= 0:
            continue

        if available_masses is not None:
            if not any(abs(m - mass) < 0.5 for m in available_masses):
                continue

        nominal = round(mass)
        interferences = get_interferences_for_mass(nominal)

        iso_score = score_isotope(
            mass, abundance, interferences,
            abundance_weight, interference_weight, min_abundance
        )

        candidates.append({
            'mass': mass,
            'abundance': abundance,
            'label': label,
            'score': iso_score,
            'interferences': interferences,
            'nominal_mass': nominal
        })

    if not candidates:
        return None

    candidates.sort(key=lambda x: x['score'], reverse=True)
    return candidates[0]


def build_smart_preferred_isotopes(elements_data: list,
                                    available_masses: list = None) -> dict:
    """
    Build a complete preferred isotopes dictionary using smart scoring.

    This replaces the hardcoded PREFERRED_ISOTOPES dict in IsotopeDisplay.

    Args:
        elements_data: List of element dicts from PeriodicTableWidget
        available_masses: Optional list of available masses

    Returns:
        Dict mapping element symbol to preferred isotope label string
        e.g. {'Ca': '44Ca', 'Fe': '57Fe', 'Au': '197Au'}
    """
    preferred = {}

    for element in elements_data:
        symbol = element.get('symbol', '')
        best = get_best_isotope(element, available_masses)
        if best:
            preferred[symbol] = best['label']

    return preferred


def get_isotope_interference_summary(element_data: dict,
                                      available_masses: list = None) -> list:
    """
    Get a summary of all isotopes for an element with their interference
    status, for display in the periodic table isotope panel.

    Args:
        element_data: Element dict from PeriodicTableWidget
        available_masses: Optional list of available masses

    Returns:
        List of dicts with keys:
            mass, abundance, label, nominal_mass,
            has_interference, worst_severity, interferences, score
        Sorted by mass.
    """
    symbol = element_data.get('symbol', '')
    isotopes = element_data.get('isotopes', [])
    summary = []

    for iso in isotopes:
        if not isinstance(iso, dict):
            continue

        mass = iso.get('mass', 0)
        abundance = iso.get('abundance', 0)
        label = iso.get('label', f'{round(mass)}{symbol}')

        if abundance <= 0:
            continue

        if available_masses is not None:
            if not any(abs(m - mass) < 0.5 for m in available_masses):
                continue

        nominal = round(mass)
        interferences = get_interferences_for_mass(nominal)
        worst = get_worst_severity(interferences)
        iso_score = score_isotope(mass, abundance, interferences)

        summary.append({
            'mass': mass,
            'abundance': abundance,
            'label': label,
            'nominal_mass': nominal,
            'has_interference': len(interferences) > 0,
            'worst_severity': worst,
            'interferences': interferences,
            'score': iso_score
        })

    summary.sort(key=lambda x: x['mass'])
    return summary