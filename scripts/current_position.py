from textual.widgets import Static
from textual.reactive import reactive

class CurrentPositionDisplay(Static):
    """A widget to display the current position"""
    current_position = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        self.update("Current position: \n" + str(self.current_position))

    def watch_current_position(self) -> None:
        """Automatically (via Textual) update listen for changes to current_position"""
        self.update("Current position: \n" + str(self.current_position))

    def update_current_position(self, new_position: float) -> None:
        self.current_position = new_position