import re

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