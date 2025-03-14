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