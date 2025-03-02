from textual.app import App
from textual.widgets import Header, Footer, Button
from textual.containers import Container
from stepper_motor import StepperMotor
from textual.app import App, ComposeResult

class Scant(App):
    """The main application."""
    CSS_PATH = "main.tcss"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app"""
        yield Header()
        yield Container(
            Button("On All", id="power_all", variant="default"),
            Button("Energize All", id="energize_all", variant="default"),
            Button("Scan All", id="scan_all", variant="success"),
            Button("Stop All", id="stop_all", variant="error"),
            id="control_buttons"
        )
        yield Container(*[StepperMotor(id=f"stepper_motor_{i+1}") for i in range(3)], id="motors")
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
    app = Scant()
    app.run()
