from typing import Optional, override

import numpy as np

from tools.mass_fraction_calculator_utils.formula_utils import element_from_label
from utils.utils import mass_to_diameter
from .element_data_builder import ResultDataBuilder
from tools.nanoparticle_shape.nanoparticle_shapes import SphereNPS, Compound


class SphereDataBuilder(ResultDataBuilder):
    def __init__(self,
                 sphere_nps: SphereNPS,
                 tracked_elements: list[str],
                 next: Optional[ResultDataBuilder] = None):
        super().__init__(next)
        self.sphere_nps: SphereNPS = sphere_nps
        self.periodic_table_info = None
        self.tracked_elements: list[str] = tracked_elements
        self.required_elements: set[str] = set()

    @override
    def init(self):
        self.set_required_elements()

        super().init()

    def set_required_elements(self):
        elements_in_nps = set(self.sphere_nps.formula.get_elements_with_counts().keys()) # TODO: review the interface
        self.required_elements = elements_in_nps.intersection(self.tracked_elements)

    @override
    def build_on(self, particle: dict) -> dict:
        """
        Args:
            particle (dict):
                The particle passed in the `ElementDataBuilder`.
                The minimal viable information is :

                - elements
                - element_mass_fg

        Returns:
            dict:
                The same ``dict`` as the argument with the following
                added information :

                - sphere_<nps_name> :
                    - mass_fg
                    - calculated_mass_fg
                    - diameter_nm
                    - radius_nm
                    - volume_nm3
                    - mass_fraction
                    - densities_used

        TODO:
            restructure with sub methods.
        """
        # Make sure that all required elements are there
        elements_in_particle = set([element_from_label(key)
                                    for key in particle.get("elements", {}).key()])

        if elements_in_particle != self.required_elements:
            return super().build_on(particle)

        # Create the sphere info
        particle_name = f"sphere_{self.sphere_nps.get_name()}"

        if particle_name not in particle:
            nps_info = particle[particle_name] = {}
        else:
            nps_info = particle[particle_name]

        known_mass_fraction = self._get_known_mass_fraction(self.sphere_nps.formula)

        known_mass_fg = nps_info["mass_fg"] = particle["totals"]["total_element_mass_fg"]
        calculated_mass_fg = nps_info["calculated_mass_fg"] = known_mass_fg / known_mass_fraction

        diameter_nm = mass_to_diameter(calculated_mass_fg, self.sphere_nps.formula.density) # TODO: nps interface is not clean
        if np.isnan(diameter_nm):
            diameter_nm = 0

        nps_info["diameter_nm"] =  diameter_nm
        radius = nps_info["radius_nm"] =  diameter_nm / 2
        nps_info["volume_nm3"] = (4/3) *  np.pi * radius**3

        nps_info["densities"] = { # TODO: interface is not pretty
            self.sphere_nps.formula.formula: self.sphere_nps.formula.density
        }

        nps_info["mass_fractions"] = { # TODO: interface is not pretty
            self.sphere_nps.formula.formula: known_mass_fraction,
        }

        return super().build_on(particle)

    def _get_known_mass_fraction(self, compound: Compound) -> float:
        """
        Gets the known mass fraction based on the compound's elements and the
        required elements.

        Returns:
            The mass fraction for the compound
        """
        total_mass = 0
        known_mass = 0
        for element, count in compound.get_elements_with_counts():
            molar_mass_with_count = count * self.periodic_table_info.get_mass(element)
            total_mass += molar_mass_with_count
            if element in self.required_elements:
                known_mass += molar_mass_with_count

        return known_mass / total_mass
