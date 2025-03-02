from textual.widgets import Static
from textual.reactive import reactive

class TargetPositionDisplay(Static):
    """A widget to display the target position the stepper motor is moving to"""
    target_position = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        self.update("Target position: \n" + str(self.target_position))

    def watch_target_position(self) -> None:
        """Automatically (via Textual) update listen for changes to target_position"""
        self.update("Target position: \n" + str(self.target_position))

    def update_target_position(self, new_position: float) -> None:
        self.target_position = new_position