from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Button
from stepper_motor import StepperMotor
from camera import CameraManager
from utils import ScanState
from settings import SettingsManager

class ScannerApp(App):
    """A Textual app for controlling stepper motors and camera."""
    
    CSS_PATH = "main.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
    ]
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Initialize settings manager without arguments
        # The SettingsManager likely has a hardcoded path or uses a default
        self.settings_manager = SettingsManager()
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        # Main app container as a vertical layout
        with Container(id="app_container"):
            # Control buttons for all motors at the very top
            with Horizontal(id="control_buttons"):
                yield Button("Home All", id="home_all_btn", variant="primary")
                yield Button("Stop All", id="stop_all_btn", variant="error")
            
            # Stepper motors in a vertical container to show in a column
            with Vertical(id="stepper_container"):
                # Create stepper motors with just id and name parameters
                for i in range(1, 4):  # Assuming we have 3 steppers
                    stepper_key = f"stepper_{i}"
                    if stepper_key in self.settings_manager.settings:
                        # Get the axis name from settings to use as the motor name
                        axis = self.settings_manager.settings[stepper_key].get("axis", f"Motor {i}")
                        yield StepperMotor(id=stepper_key, name=axis)
            
            # Camera manager below the control buttons
            yield CameraManager(settings_manager=self.settings_manager)
        
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the main app"""
        if event.button.id == "home_all_btn":
            # Press the home button on all motors
            for motor in self.query(StepperMotor):
                home_button = motor.query_one("#home_stepper")
                home_button.press()
        
        elif event.button.id == "stop_all_btn":
            # Stop scanning on all motors
            for motor in self.query(StepperMotor):
                scan_button = motor.query_one("#run_stepper")
                if scan_button.label == "Stop":  # Only stop if currently scanning
                    scan_button.press()

if __name__ == "__main__":
    app = ScannerApp()
    app.run()
