"""
This file contains code that help the Mass Fraction Calculator to share its
data with other parts of the code.
"""

from widget.periodic_table_widget import PeriodicTableWidget


class MassFractionService:
    """Is the manager and provider for Mass Fractions data"""
    def __init__(self, periodic_table: PeriodicTableWidget):
        self.element_mass_fractions = {}
        self.element_densities = {}
        self.element_molecular_weights = {}

        self.sample_mass_fractions = {}
        self.sample_densities = {}
        self.sample_molecular_weights = {}

        self.periodic_table = periodic_table  # TODO: Make it a information service to simplify everything

    def set_element_infos(self,
                          mass_fractions: dict,
                          densities: dict,
                          molecular_weights:dict) -> None:
        """
        Updates element level information.
        Args:
            mass_fractions: Mass fractions at an element level
            densities: Densities at an element level
            molecular_weights: Molecular weights at an element level
        """
        self.element_mass_fractions = mass_fractions.copy()
        self.element_densities = densities.copy()
        self.element_molecular_weights = molecular_weights.copy()

    def set_sample_infos(self,
                         mass_fractions: dict,
                         densities: dict,
                         molecular_weights: dict,
                         selected_samples: list[str]) -> None:
        """
        Updates sample level information for selected samples
        Args:
            mass_fractions: Mass fractions at a sample level
            densities: Densities at a sample level
            molecular_weights: Molecular weights at a sample level
            selected_samples: Samples selected for the change.
        """
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

    def get_mass_fraction(self, element_key, sample_name=None):
        """Get mass fraction for element in compound.

        Returns:
            float: Mass fraction (0.0-1.0), defaults to 1.0 for pure element
        """
        element = element_key.split('-')[0]

        if sample_name and sample_name in self.sample_mass_fractions:
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

    def reset(self):
        """Resets all data structures of the service."""
        self.element_mass_fractions: dict = {}
        self.element_densities: dict = {}
        self.element_molecular_weights: dict = {}

        self.sample_mass_fractions: dict = {}
        self.sample_densities: dict = {}
        self.sample_molecular_weights: dict = {}

    def add_fingerprint_to(self, crypto):
        """
        Adds the mass fraction's fingerprint to the updatable hash
        object/algorithm.
        Args:
            crypto: Hash object that needs the mass fraction signature.
        """
        crypto.update(repr(self.element_mass_fractions).encode('utf-8', 'replace'))
        crypto.update(repr(self.element_densities).encode('utf-8', 'replace'))
        crypto.update(repr(self.sample_mass_fractions).encode('utf-8', 'replace'))
        crypto.update(repr(self.sample_densities).encode('utf-8', 'replace'))
