from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.widgets import Header, Footer, Button
from stepper_motor import StepperMotor
from camera import CameraManager
from utils import ScanState

class ScannerApp(App):
    """A Textual app for controlling stepper motors and camera."""
    
    CSS_PATH = "main.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
    ]
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header()
        
        # Main app container as a vertical layout
        with Vertical(id="app_container"):
            # Control buttons for all motors at the very top
            with Horizontal(id="control_buttons"):
                yield Button("Power All", id="power_all")
                yield Button("Energize All", id="energize_all")
                yield Button("Scan All", id="scan_all")
                yield Button("Stop All", id="stop_all")
            
            # Camera manager below the control buttons
            yield CameraManager()
            
            # Stepper motors in a vertical container to show in a column
            with Vertical(id="stepper_container"):
                yield StepperMotor(id="stepper_1", name="Yaw")
                yield StepperMotor(id="stepper_2", name="Tilt")
                yield StepperMotor(id="stepper_3", name="Forward")
        
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the main app"""
        if event.button.id == "power_all":
            # Press the power button on all motors
            for motor in self.query(StepperMotor):
                power_button = motor.query_one("#power_stepper")
                power_button.press()
        
        elif event.button.id == "energize_all":
            # Press the energize button on all motors
            for motor in self.query(StepperMotor):
                energize_button = motor.query_one("#energize_stepper")
                energize_button.press()
        
        elif event.button.id == "scan_all":
            # Start scanning on all motors that are ready
            for motor in self.query(StepperMotor):
                if motor.initialized and motor.energized and motor.validate_scan_parameters():
                    scan_button = motor.query_one("#run_stepper")
                    if scan_button.label == "Scan":  # Only start if not already scanning
                        scan_button.press()
        
        elif event.button.id == "stop_all":
            # Stop scanning on all motors
            for motor in self.query(StepperMotor):
                scan_button = motor.query_one("#run_stepper")
                if scan_button.label == "Stop":  # Only stop if currently scanning
                    scan_button.press()

if __name__ == "__main__":
    app = ScannerApp()
    app.run()
