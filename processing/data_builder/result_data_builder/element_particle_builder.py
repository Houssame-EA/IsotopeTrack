"""
This file describes the base classes for the data builders. In this context,
data builders are classes that will add information to a ``dict``. The builders
will use a chain of responsibility pattern so multiple NPSs can be selected at once.
"""
from typing import Callable, override

import numpy as np

from tools.mass_fraction_utils import MassFractionService
from particle_builder import ParticleBuilder
from tools.periodic_table_utils.periodic_table_info import PeriodicTableInfo
from utils.particles import mass_to_diameter


class ElementDataBuilder(ParticleBuilder):
    def __init__(self,
                 update_element_cache: Callable[[], dict],
                 mass_fraction_service: MassFractionService,
                 periodic_table_info: PeriodicTableInfo):
        super().__init__()
        self.update_element_cache = update_element_cache
        self.element_cache: dict = {}

        self.mass_fraction_service: MassFractionService = mass_fraction_service
        self.periodic_table_info: PeriodicTableInfo = periodic_table_info

    @override
    def init(self):
        self.element_cache = self.update_element_cache()
        super().init()

    @override
    def build(self, particle: dict) -> dict:
        """
        Args:
            particle (dict):
                The particule in its original state. The minimal viable information is :

                - ``elements``
                - ``_source_sample`` or ``source_sample``

        Return:
            dict:
                The same ``dict`` as the argument with the following added
                information:

                - element_mass_fg
                - element_moles_fmol
                - particle_mass_fg
                - particle_moles_fmol
                - element_diameter_nm
                - particle_diameter_nm
                - mass_fractions_used
                - molar_masses
                - mass_fg
                - mass_percentages
                - mole_percentages
                - totals:
                    - total_element_mass_fg
                    - total_element_moles_fmol
                    - total_particle_mass_fg
                    - total_particle_moles_fmol
                - densities_used:
                    - by isotope:
                        - compound_density
                        - element_density
        """
        if not self.initialized:
            self.init()

        sample_name = particle.get('_source_sample') # TODO: _source_sample --> source_sample
        assert sample_name is not None and isinstance(sample_name, str)

        if 'element_mass_fg' not in particle:
            particle['element_mass_fg'] = {}
        if 'element_moles_fmol' not in particle:
            particle['element_moles_fmol'] = {}
        if 'particle_mass_fg' not in particle:
            particle['particle_mass_fg'] = {}
        if 'particle_moles_fmol' not in particle:
            particle['particle_moles_fmol'] = {}
        if 'element_diameter_nm' not in particle:
            particle['element_diameter_nm'] = {}
        if 'particle_diameter_nm' not in particle:
            particle['particle_diameter_nm'] = {}
        if 'mass_fractions_used' not in particle:
            particle['mass_fractions_used'] = {}
        if 'densities_used' not in particle:
            particle['densities_used'] = {}
        if 'molar_masses' not in particle:
            particle['molar_masses'] = {}

        if 'mass_fg' not in particle:
            particle['mass_fg'] = {}

        total_element_mass_fg = 0
        total_element_moles_fmol = 0
        total_particle_mass_fg = 0
        total_particle_moles_fmol = 0

        for element_display, counts in particle['elements'].items():
            if counts <= 0:
                continue

            if element_display in self.element_cache:
                cache_entry = self.element_cache[element_display]
                conversion_factor = cache_entry['conversion_factor']
                element_key = cache_entry['element_key']

                element = element_key.split('-')[0]
                isotope = float(element_key.split('-')[1])
                atomic_mass = self.periodic_table_info.get_mass_by_element(element) or float(isotope)

                mass_fraction = self.mass_fraction_service.get_mass_fraction(element_key, sample_name)
                compound_density = self.mass_fraction_service.get_element_density(element_key, sample_name)

                element_density = self.periodic_table_info.get_density_by_element(element)

                particle['mass_fractions_used'][element_display] = mass_fraction
                particle['densities_used'][element_display] = {
                    'element_density': element_density,
                    'compound_density': compound_density
                }
                particle['molar_masses'][element_display] = atomic_mass

                if conversion_factor and conversion_factor > 0 and atomic_mass > 0:

                    element_mass_fg = counts / conversion_factor
                    element_moles_fmol = element_mass_fg / atomic_mass

                    particle['element_mass_fg'][element_display] = element_mass_fg
                    particle['element_moles_fmol'][element_display] = element_moles_fmol

                    particle_mass_fg = element_mass_fg / mass_fraction

                    compound_molecular_weight = self.mass_fraction_service.get_molecular_weight(element_key,
                                                                                                sample_name)

                    if compound_molecular_weight and compound_molecular_weight > 0:
                        particle_moles_fmol = particle_mass_fg / compound_molecular_weight
                    else:
                        particle_moles_fmol = element_moles_fmol

                    particle['particle_mass_fg'][element_display] = particle_mass_fg
                    particle['particle_moles_fmol'][element_display] = particle_moles_fmol

                    if element_density and element_density > 0:
                        element_diameter_nm = mass_to_diameter(element_mass_fg, element_density)
                        if not np.isnan(element_diameter_nm):
                            particle['element_diameter_nm'][element_display] = element_diameter_nm
                        else:
                            particle['element_diameter_nm'][element_display] = 0
                    else:
                        particle['element_diameter_nm'][element_display] = 0

                    if compound_density and compound_density > 0:
                        particle_diameter_nm = mass_to_diameter(particle_mass_fg, compound_density)
                        if not np.isnan(particle_diameter_nm):
                            particle['particle_diameter_nm'][element_display] = particle_diameter_nm
                        else:
                            particle['particle_diameter_nm'][element_display] = 0
                    else:
                        particle['particle_diameter_nm'][element_display] = particle['element_diameter_nm'][
                            element_display]

                    particle['mass_fg'][element_display] = particle_mass_fg

                    total_element_mass_fg += element_mass_fg
                    total_element_moles_fmol += element_moles_fmol
                    total_particle_mass_fg += particle_mass_fg
                    total_particle_moles_fmol += particle_moles_fmol

                else:
                    particle['element_mass_fg'][element_display] = 0
                    particle['element_moles_fmol'][element_display] = 0
                    particle['particle_mass_fg'][element_display] = 0
                    particle['particle_moles_fmol'][element_display] = 0
                    particle['element_diameter_nm'][element_display] = 0
                    particle['particle_diameter_nm'][element_display] = 0
                    particle['mass_fg'][element_display] = 0

        particle['totals'] = {
            'total_element_mass_fg': total_element_mass_fg,
            'total_element_moles_fmol': total_element_moles_fmol,
            'total_particle_mass_fg': total_particle_mass_fg,
            'total_particle_moles_fmol': total_particle_moles_fmol
        }

        if total_element_mass_fg > 0:
            particle['mass_percentages'] = {}
            particle['mole_percentages'] = {}

            for element_display in particle['elements'].keys():
                if element_display in particle['element_mass_fg']:
                    element_mass = particle['element_mass_fg'][element_display]
                    element_moles = particle['element_moles_fmol'][element_display]

                    mass_percent = (element_mass / total_element_mass_fg * 100) if total_element_mass_fg > 0 else 0
                    mole_percent = (
                            element_moles / total_element_moles_fmol * 100) if total_element_moles_fmol > 0 else 0

                    particle['mass_percentages'][element_display] = mass_percent
                    particle['mole_percentages'][element_display] = mole_percent

        return particle
