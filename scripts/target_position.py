from textual.widgets import Static
from textual.reactive import reactive
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class TargetPositionDisplay(Static):
    """A widget to display the target position the stepper motor is moving to"""
    target_position = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        logger.debug(f"Mounting TargetPositionDisplay with initial value: {self.target_position}")
        self.update("Target position: \n" + str(self.target_position))

    def watch_target_position(self) -> None:
        """Automatically (via Textual) update listen for changes to target_position"""
        logger.debug(f"Target position changed to: {self.target_position}")
        self.update("Target position: \n" + str(self.target_position))

    def update_target_position(self, new_position: float) -> None:
        """Update the target position value"""
        try:
            logger.debug(f"Updating target position from {self.target_position} to {new_position}")
            self.target_position = new_position
        except Exception as e:
            logger.error(f"Error updating target position: {e}")