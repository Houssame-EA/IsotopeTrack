import re

def extract_mass_and_element(element_name):
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

def sort_element_dict_by_mass(element_dict):
    if not element_dict:
        return element_dict
    
    sorted_elements = sort_elements_by_mass(list(element_dict.keys()))
    
    return {element: element_dict[element] for element in sorted_elements}


def element_alphabetical_key(label):
    """Sort key that sorts by chemical symbol, ignoring any leading mass number.

    e.g. '107Ag' and 'Ag' both sort under 'ag', '55Fe' under 'fe'.
    """
    text = str(label).strip()
    match = re.match(r'^\d*([A-Za-z][A-Za-z]?)', text)
    symbol = match.group(1) if match else text
    return symbol.casefold()