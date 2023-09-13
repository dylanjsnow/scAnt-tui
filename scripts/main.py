import subprocess

from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Button, Static, Select, Label
from textual.containers import ScrollableContainer
from textual.reactive import reactive
from textual_slider import Slider

def get_stepper_motor_serial_numbers():
    print("Print out all current TIC stepper motors connected via USB")
    print(r'Run "ticcmd --list" to get a list of all connected Tic devices.')
    print("Extract just the first number from each line e.g")
    print("'00425332,         Tic T500 Stepper Motor Controller            ' returns '00425332'")
    motor_serial_numbers = subprocess.check_output(["ticcmd", "--list"]).decode("utf-8").splitlines()
    motor_serial_numbers = [line.split(",")[0] for line in motor_serial_numbers]
    print("Serial numbers of all connected Tic devices: ", motor_serial_numbers)

    return motor_serial_numbers

class StepperMotor(Static):
    """A stepper motor interface"""

    axis = reactive("X")
    axes = ["X", "Y", "Z"]
    serial_number = reactive("0")
    serial_numbers = get_stepper_motor_serial_numbers()
    current_position = reactive(0)
    target_position = reactive(0)
    max_value = reactive(0)
    min_value = reactive(0)
    home_position = reactive(0)
    moving = reactive(False)

    def reset(self):
        self.axis = "X"
        self.serial_number = "0"
        self.current_position = 0
        self.target_position = 0
        self.max_value = 0
        self.min_value = 0
        self.home_position = 0
        self.moving = False

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button press"""
        if event.button.id == "energize_stepper":
            self.add_class("energized")
        elif event.button.id == "deenergize_stepper":
            self.remove_class("energized")
        elif event.button.id == "home_stepper":
            pass

    def on_slider_changed(self, event: Slider.Changed) -> None:
        """Handle a slider change"""
        print("Slider changed to: ", event.slider.value)

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle a select change"""
        print("Select changed to: ", event.select.value)

    def compose(self) -> ComposeResult:
        """Create child widgets for the stepper motor"""
        yield Button("Energize", id="energize_stepper", variant="success")
        yield Button("Deenergize", id="deenergize_stepper", variant="error")
        yield Button("Home", id="home_stepper", variant="warning")
        yield Slider(0, 100, 50, id="position_stepper")
        yield Label("Axis: ", id="axis_label")
        yield Select(((axis, axis) for axis in self.axes), id="axis_stepper")
        yield Label("Serial: ", id="serial_label")
        yield Select(((serial, serial) for serial in self.serial_numbers), id="serial_stepper")

class Scant(App):
    """The main application."""
    CSS_PATH = "main.tcss"
    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        self.dark = True

    def compose(self) -> ComposeResult:
        """Create child widgets for the app"""
        yield Header()
        yield Footer()
        yield ScrollableContainer(StepperMotor(), StepperMotor(), StepperMotor(), id="scant")
    
    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

if __name__ == "__main__":
    app = Scant()
    app.run()
