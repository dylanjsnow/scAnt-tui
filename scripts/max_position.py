from textual.widgets import Static
from textual.reactive import reactive
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class MaxPositionDisplay(Static):
    """A widget to display the maximum value the stepper motor can move to"""
    max_position = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        logger.debug(f"Mounting MaxPositionDisplay with initial value: {self.max_position}")
        self.update("Maximum position: \n" + str(self.max_position))

    def watch_max_position(self) -> None:
        """Automatically (via Textual) update listen for changes to max_position"""
        logger.debug(f"Maximum position changed to: {self.max_position}")
        self.update("Maximum position: \n" + str(self.max_position))

    def update_max_position(self, new_position: float) -> None:
        """Update the maximum position value"""
        try:
            logger.debug(f"Updating maximum position from {self.max_position} to {new_position}")
            self.max_position = new_position
        except Exception as e:
            logger.error(f"Error updating maximum position: {e}")