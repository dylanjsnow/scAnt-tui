from textual.widgets import Static
from textual.reactive import reactive
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class CurrentLimitDisplay(Static): 
    """A widget to display the current limit of the stepper motor"""
    current_limit = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        logger.debug(f"Mounting CurrentLimitDisplay with initial value: {self.current_limit}")
        self.update("Current limit: \n" + str(self.current_limit))

    def watch_current_limit(self) -> None:
        """Automatically (via Textual) update listen for changes to current_limit"""
        logger.debug(f"Current limit changed to: {self.current_limit}")
        self.update("Current limit: \n" + str(self.current_limit))

    def update_current_limit(self, new_limit: float) -> None:
        """Update the current limit value"""
        try:
            logger.debug(f"Updating current limit from {self.current_limit} to {new_limit}")
            self.current_limit = new_limit
        except Exception as e:
            logger.error(f"Error updating current limit: {e}")