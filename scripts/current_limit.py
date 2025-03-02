from textual.widgets import Static
from textual.reactive import reactive

class CurrentLimitDisplay(Static): 
    """A widget to display the current limit of the stepper motor"""
    current_limit = reactive(0)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        self.update("Current limit: \n" + str(self.current_limit))

    def watch_current_limit(self) -> None:
        """Automatically (via Textual) update listen for changes to current_limit"""
        self.update("Current limit: \n" + str(self.current_limit))

    def update_current_limit(self, new_limit: float) -> None:
        self.current_limit = new_limit