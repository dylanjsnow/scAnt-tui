from textual.widgets import Static
from textual.reactive import reactive
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class MinPositionDisplay(Static):
    """A widget to display the minimum value the stepper motor can move to"""
    min_position = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        logger.debug(f"Mounting MinPositionDisplay with initial value: {self.min_position}")
        self.update("Minimum position: \n" + str(self.min_position))

    def watch_min_position(self) -> None:
        """Automatically (via Textual) update listen for changes to min_position"""
        logger.debug(f"Minimum position changed to: {self.min_position}")
        self.update("Minimum position: \n" + str(self.min_position))

    def update_min_position(self, new_position: float) -> None:
        """Update the minimum position value"""
        try:
            logger.debug(f"Updating minimum position from {self.min_position} to {new_position}")
            self.min_position = new_position
        except Exception as e:
            logger.error(f"Error updating minimum position: {e}")