from PySide6.QtWidgets import QTableWidgetItem
import logging
_itk_log = logging.getLogger("IsotopeTrack.widget.numeric_table")


class NumericTableWidgetItem(QTableWidgetItem):
    def __lt__(self, other):
        """
        Compare two table items numerically for sorting purposes.
        
        Args:
            other: Another QTableWidgetItem to compare against
            
        Returns:
            bool: True if this item's numeric value is less than the other item's value
        """
        try:
            self_text = self.text().strip()
            other_text = other.text().strip()
            
            if self_text == "N/A":
                return False
            if other_text == "N/A":
                return True
            
            self_value = float(self_text)
            other_value = float(other_text)
            
            return self_value < other_value
        except ValueError:
            _itk_log.exception("Handled exception in __lt__")
            return self.text() < other.text()