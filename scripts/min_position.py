from textual.widgets import Static
from textual.reactive import reactive

class MinPositionDisplay(Static):
    """A widget to display the minimum value the stepper motor can move to"""
    min_position = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        self.update("Minimum position: \n" + str(self.min_position))

    def watch_min_position(self) -> None:
        """Automatically (via Textual) update listen for changes to min_position"""
        self.update("Minimum position: \n" + str(self.min_position))

    def update_min_position(self, new_position: float) -> None:
        self.min_position = new_position