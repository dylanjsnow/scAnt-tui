from textual.widgets import Static
from textual.reactive import reactive
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class CurrentPositionDisplay(Static):
    """A widget to display the current position"""
    current_position = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        logger.debug(f"Mounting CurrentPositionDisplay with initial value: {self.current_position}")
        self.update("Current position: \n" + str(self.current_position))

    def watch_current_position(self) -> None:
        """Automatically (via Textual) update listen for changes to current_position"""
        logger.debug(f"Current position changed to: {self.current_position}")
        self.update("Current position: \n" + str(self.current_position))

    def update_current_position(self, new_position: float) -> None:
        """Update the current position value"""
        try:
            logger.debug(f"Updating current position from {self.current_position} to {new_position}")
            self.current_position = new_position
        except Exception as e:
            logger.error(f"Error updating current position: {e}")