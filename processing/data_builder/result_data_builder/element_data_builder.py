"""
TODO: docstring
"""
from typing import override, Optional, Callable

import numpy as np

from utils.utils import mass_to_diameter
from result_data_builder import ResultDataBuilder
from widget.periodic_table_widget import PeriodicTableWidget


class ElementDataBuilder(ResultDataBuilder):
    """
    TODO: Docstring
    """

    def __init__(self,
                 update_element_cache: Callable[[], dict],
                 next: Optional[ResultDataBuilder] = None):
        """
        Args:
            next: next chain node in the builder.
        """
        super().__init__(next)

        # TODO: Provide les informations à partir d'un service

        self.update_element_cache = update_element_cache
        self.element_cache: dict = {}
        self.periodic_table: Optional[PeriodicTableWidget] = None

        self.element_mass_fractions: dict = {}
        self.element_densities: dict = {}
        self.element_molecular_weights: dict = {}

        self.sample_mass_fractions: dict = {}
        self.sample_densities: dict = {}
        self.sample_molecular_weights: dict = {}

        # TODO: Faire comme le update_element_cache,
        #  mais pour les mass_fraction, densities et molecular_weights
        self.current_sample: str = ""

    @override
    def init(self):
        self.element_cache = self.update_element_cache()

        if self.periodic_table is None:
            raise RuntimeError("self.periodic_table was not initialized in time.")

        super().init()

    @override
    def build_on(self, particle: dict) -> dict:
        """
        Args:
            particle (dict):
                The particule in its original state. The minimal viable information is :

                - elements

        Return:
            dict:
                The same ``dict`` as the argument with the following added
                information:

                - element_mass_fg
                - element_moles_fmol
                - particle_mass_fg TODO: Check if we want to keep the particle information
                - particle_moles_fmol TODO: Check if we want to keep the particle information
                - element_diameter_nm
                - particle_diameter_nm TODO: Check if we want to keep the particle information
                - mass_fractions_used TODO: Check if we want to keep the particle information
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
                        - compound_density TODO: Check if we want to keep the particle information
                        - element_density

        Todo:
            - Check if we want to keep the particle information
        """
        if not self.initialized:
            self.init()

        assert self.periodic_table is not None

        sample_name = particle.get('_source_sample', self.current_sample)

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
                if self.periodic_table:
                    element_data = self.periodic_table.get_element_by_symbol(element)
                    if element_data:
                        atomic_mass = float(element_data.get('mass', isotope))

                mass_fraction = self.get_mass_fraction(element_key, sample_name)
                element_density = None
                compound_density = self.get_element_density(element_key, sample_name)

                if self.periodic_table:
                    element_data = self.periodic_table.get_element_by_symbol(element)
                    if element_data:
                        element_density = element_data.get('density')

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

                    compound_molecular_weight = self.get_molecular_weight(element_key, sample_name)

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

        return super().build_on(particle)

    def get_mass_fraction(self, element_key, sample_name=None):
        """Get mass fraction for element in compound.

        Returns:
            float: Mass fraction (0.0-1.0), defaults to 1.0 for pure element
        """
        element = element_key.split('-')[0]

        if sample_name and sample_name in self.sample_mass_fractions:
            print("mass fraction through sample")
            fraction = self.sample_mass_fractions[sample_name].get(element)
            if fraction is not None:
                return fraction

        if element in self.element_mass_fractions:
            return self.element_mass_fractions[element]

        return 1.0

    def get_molecular_weight(self, element_key, sample_name=None):
        """Get molecular weight for element compound.

        Returns:
            float or None: Molecular weight in g/mol
        """
        element = element_key.split('-')[0]

        if (sample_name and
                hasattr(self, 'sample_molecular_weights') and
                sample_name in self.sample_molecular_weights):
            print("molecular weight through sample")
            molecular_weight = self.sample_molecular_weights[sample_name].get(element)
            if molecular_weight and molecular_weight > 0:
                return molecular_weight

        if (hasattr(self, 'element_molecular_weights') and
                element in self.element_molecular_weights):
            molecular_weight = self.element_molecular_weights[element]
            if molecular_weight and molecular_weight > 0:
                return molecular_weight

        if self.periodic_table:
            element_data = self.periodic_table.get_element_by_symbol(element)
            if element_data:
                atomic_mass = float(element_data.get('mass', 0))
                return atomic_mass

        return None

    def get_element_density(self, element_key, sample_name=None):
        """Get density for element compound.

        Returns:
            float or None: Density in g/cm³
        """
        element = element_key.split('-')[0]

        if sample_name and sample_name in self.sample_densities:
            print("density through sample")
            density = self.sample_densities[sample_name].get(element)
            if density:
                return density

        if element in self.element_densities:
            return self.element_densities[element]

        if self.periodic_table:
            element_data = self.periodic_table.get_element_by_symbol(element)
            if element_data:
                return element_data.get('density', None)

        return None

    def set_for_all(self, mass_fractions: dict, densities: dict, molecular_weights: dict):
        self.element_mass_fractions = mass_fractions.copy()
        self.element_densities = densities.copy()
        self.element_molecular_weights = molecular_weights.copy()

    def set_for_selected_samples(self, mass_fractions, densities, molecular_weights, selected_samples):
        for sample_name in selected_samples:
            if sample_name not in self.sample_mass_fractions:
                self.sample_mass_fractions[sample_name] = {}
            if sample_name not in self.sample_densities:
                self.sample_densities[sample_name] = {}
            if not hasattr(self, 'sample_molecular_weights'):
                self.sample_molecular_weights = {}
            if sample_name not in self.sample_molecular_weights:
                self.sample_molecular_weights[sample_name] = {}

            self.sample_mass_fractions[sample_name].update(mass_fractions.copy())
            self.sample_densities[sample_name].update(densities.copy())
            self.sample_molecular_weights[sample_name].update(molecular_weights.copy())

    def reset(self):
        self.element_mass_fractions: dict = {}
        self.element_densities: dict = {}
        self.element_molecular_weights: dict = {}

        self.sample_mass_fractions: dict = {}
        self.sample_densities: dict = {}
        self.sample_molecular_weights: dict = {}
