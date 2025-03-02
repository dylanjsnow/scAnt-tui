from textual.widgets import Static
from textual.reactive import reactive

class MaxPositionDisplay(Static):
    """A widget to display the maximum value the stepper motor can move to"""
    max_position = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        self.update("Maximum position: \n" + str(self.max_position))

    def watch_max_position(self) -> None:
        """Automatically (via Textual) update listen for changes to max_position"""
        self.update("Maximum position: \n" + str(self.max_position))

    def update_max_position(self, new_position: float) -> None:
        self.max_position = new_position