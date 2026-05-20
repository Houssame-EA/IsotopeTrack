import re

_ELEMENT_SYMBOLS = {
    'H', 'He', 'Li', 'Be', 'B', 'C', 'N', 'O', 'F', 'Ne',
    'Na', 'Mg', 'Al', 'Si', 'P', 'S', 'Cl', 'Ar', 'K', 'Ca',
    'Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
    'Ga', 'Ge', 'As', 'Se', 'Br', 'Kr', 'Rb', 'Sr', 'Y', 'Zr',
    'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd', 'In', 'Sn',
    'Sb', 'Te', 'I', 'Xe', 'Cs', 'Ba', 'La', 'Ce', 'Pr', 'Nd',
    'Pm', 'Sm', 'Eu', 'Gd', 'Tb', 'Dy', 'Ho', 'Er', 'Tm', 'Yb',
    'Lu', 'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg',
    'Tl', 'Pb', 'Bi', 'Po', 'At', 'Rn', 'Fr', 'Ra', 'Ac', 'Th',
    'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk', 'Cf', 'Es', 'Fm',
    'Md', 'No', 'Lr', 'Rf', 'Db', 'Sg', 'Bh', 'Hs', 'Mt', 'Ds',
    'Rg', 'Cn', 'Nh', 'Fl', 'Mc', 'Lv', 'Ts', 'Og',
}

def extract_mass_and_element(element_name):
    """ 
    Args:
        element_name (str): Element name string, potentially with mass number prefix (e.g., '55Fe', 'Fe')
    
    Returns:
        tuple: (mass, element) where mass is an integer and element is a string
               Returns (999, element_name) if no mass number is found
    """
    element_name = element_name.strip()
             
    match = re.match(r'^(\d+)([A-Za-z]+)', element_name)
    if match:
        mass = int(match.group(1))
        element = match.group(2)
        return mass, element
             
    return 999, element_name

def sort_elements_by_mass(elements):
    """
    Sort elements by mass number from low to high.
    
    Sorts a list of element names based on their mass numbers extracted from
    the element name string. Elements without mass numbers are sorted last.
    
    Args:
        elements (list): List of element name strings
    
    Returns:
        list: Sorted list of element name strings ordered by mass number (ascending)
    """
    def get_sort_key(element):
        """
        Args:
            element (Any): The element.
        Returns:
            object: Result of the operation.
        """
        mass, _ = extract_mass_and_element(element)
        return mass
             
    return sorted(elements, key=get_sort_key)

def format_element_label(element_name, show_mass_numbers):
    """
    Args:
        element_name (str): Element name string, potentially with mass number prefix
        show_mass_numbers (bool): If True, keep mass numbers; if False, remove them
    
    Returns:
        str: Formatted element label (e.g., '55Fe' or 'Fe')
    """
    if not show_mass_numbers:
        mass, element = extract_mass_and_element(element_name)
        return element
    else:
        return element_name.strip()

def format_combination_label(combination, show_mass_numbers):
    """
    
    Args:
        combination (str): Comma-separated element names (e.g., '56Fe, 48Ti, 63Cu')
        show_mass_numbers (bool): If True, keep mass numbers; if False, remove them
    
    Returns:
        str: Formatted combination label with elements sorted by mass (e.g., '48Ti, 55Fe, 63Cu' or 'Ti, Fe, Cu')
    """
    elements = [elem.strip() for elem in combination.split(',')]
             
    sorted_elements = sort_elements_by_mass(elements)
             
    formatted_elements = [format_element_label(elem, show_mass_numbers) for elem in sorted_elements]
             
    return ', '.join(formatted_elements)

def sort_element_dict_by_mass(element_dict):
    """    
    Args:
        element_dict (dict): Dictionary with element names as keys
    
    Returns:
        dict: New dictionary with keys sorted by mass number (ascending order)
    """
    if not element_dict:
        return element_dict
    
    sorted_elements = sort_elements_by_mass(list(element_dict.keys()))
    
    return {element: element_dict[element] for element in sorted_elements}


def _extract_element_symbol(label):
    """Extract a valid chemical symbol from a label like 197Au, Au197, or Au+."""
    text = str(label).strip()
    for token in re.findall(r'[A-Za-z]{1,2}', text):
        symbol = token[0].upper() + token[1:].lower()
        if symbol in _ELEMENT_SYMBOLS:
            return symbol
    return None


def _extract_isotope_mass(label):
    """Extract isotope mass from labels with prefix or suffix notation."""
    text = str(label).strip()
    m = re.search(r'^\s*(\d+)\s*[A-Za-z]', text)
    if m:
        return int(m.group(1))
    m = re.search(r'[A-Za-z]+\s*(\d+)\s*(?:[+-]\d*)?\s*$', text)
    if m:
        return int(m.group(1))
    return None


def element_alphabetical_key(label):
    """Sort key that prioritizes chemical symbol, then mass/label for stability."""
    text = str(label).strip()
    symbol = _extract_element_symbol(text)
    mass = _extract_isotope_mass(text)
    unknown_symbol = 1 if symbol is None else 0
    missing_mass = 1 if mass is None else 0
    symbol_key = symbol if symbol is not None else text.casefold()
    return (unknown_symbol, symbol_key, missing_mass, mass or 0, text.casefold(), text)
