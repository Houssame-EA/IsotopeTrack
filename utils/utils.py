import numpy as np


def mass_to_diameter(mass_fg, density):
    """Convert mass to spherical particle diameter.

    Returns:
        float: Diameter in nanometers
    """
    if mass_fg <= 0 or density <= 0:
        return float('nan')
    mass_g = mass_fg * 1e-15
    diameter_cm = ((6 * mass_g) / (np.pi * density)) ** (1 / 3)
    return diameter_cm * 1e7
