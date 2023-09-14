import subprocess

from textual import on
from textual import log
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Button, Static, Select, Label, Input
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

def get_axes():
    return ["X", "Y", "Z"]

class StepperMotor(Static):
    """A stepper motor interface"""

    axes = get_axes()
    axis = reactive("")
    serial_numbers = get_stepper_motor_serial_numbers()
    serial_number = reactive("")
    current_position = reactive(0)
    target_position = reactive(0)
    max_value = reactive(0)
    min_value = reactive(0)
    home_position = reactive(0)
    moving = reactive(False)
    energized = reactive(False)
    initialized = reactive(False)

    def reset(self):
        self.axis = ""
        self.serial_number = ""
        self.current_position = 0
        self.target_position = 0
        self.max_value = 0
        self.min_value = 0
        self.home_position = 0
        self.moving = False

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        self.set_interval(1 / 60.0, self.update_current_position)
        self.set_interval(1 / 60.0, self.update_is_moving)
        self.add_class("deenergized")

    def update_initialized(self, event: Button.Pressed) -> None:
        self.initialized = not self.initialized
        for button in self.query(Button):
            if button.id in ["energize_stepper", "deenergize_stepper"]:
                button.disabled = not self.initialized
        for input in self.query(Input):
            if input.id in ["target_position_stepper", "max_value_stepper", "min_value_stepper"]:
                input.disabled = not self.initialized
        if self.initialized:
            self.add_class("initialized")
        else:
            self.remove_class("initialized")
            self.remove_class("energized")
            self.remove_class("deenergized")
        for select in self.query(Select):
            if select.id in ["axis_stepper", "serial_stepper"]:
                select.disabled = self.initialized

    def update_energized(self, event: Button.Pressed) -> None:
        self.remove_class("deenergized")
        self.remove_class("initialized")
        self.add_class("energized")
        self.energized = True

    def update_deenergized(self, event: Button.Pressed) -> None:
        self.remove_class("energized")
        self.remove_class("initialized")
        self.add_class("deenergized")
        self.energized = False

    def update_target_position(self) -> None:
        """Update the target position of the stepper motor"""
        if self.energized:
            self.target_position = 1
        else:
            self.target_position = 2

    def update_is_moving(self) -> None:
        """Update the is moving state of the stepper motor"""
        if self.energized:
            self.moving = False
        else:
            self.moving = False

    def update_current_position(self) -> None:
        """Update the current position of the stepper motor"""
        if self.energized:
            self.current_position = 1
        else:
            self.current_position = 2

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button press"""
        print(self.id, " button pressed: ", event.button.id)
        
        if event.button.id == "initialize_stepper":
            self.update_initialized(event)
        elif event.button.id == "energize_stepper":
            self.update_energized(event)
        elif event.button.id == "deenergize_stepper":
            self.update_deenergized(event)
        

    @on(Slider.Changed)
    def on_slider_changed(self, event: Slider.Changed) -> None:
        """Handle a slider change"""
        print(self.id, " slider changed to: ", event.value)
        if event.slider.id == "position_stepper":
            self.target_position = event.value
            print(self.id, " target position: ", self.target_position)

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle a select change"""
        print(self.id, " select changed to: ", event.value)
        if event.select.id == "axis_stepper":
            self.axis = event.value
            print(self.id, " axis: ", self.axis)
        elif event.select.id == "serial_stepper":
            self.serial_number = event.value
            print(self.id, " serial number: ", self.serial_number)

    def compose(self) -> ComposeResult:
        """Create child widgets for the stepper motor, with a top row of changeable variables and a bottom row of fixed values"""
        yield Label("Axis: ", id="axis_label")
        yield Select(options=((axis, axis) for axis in self.axes), id="axis_stepper", value=self.axes[int(self.id.split("_")[-1]) - 1], allow_blank=False)
        yield Label("Serial: ", id="serial_label")
        yield Select(options=((serial, serial) for serial in self.serial_numbers), id="serial_stepper", value=self.serial_numbers[int(self.id.split("_")[-1]) - 1] if len(self.serial_numbers) > 0 else "", allow_blank=False)
        yield Button("Start/ Stop", id="initialize_stepper", variant="default")
        yield Button("Energize", id="energize_stepper", variant="success", disabled=True)
        yield Button("Deenergize", id="deenergize_stepper", variant="error", disabled=True)
        yield Slider(0, 100, 50, id="position_stepper")
        yield Label("Current position: ", id="current_position_label")
        yield Input(id="current_position_stepper", value=str(self.current_position), disabled=True)
        yield Label("Target position: ", id="target_position_label")
        yield Input(id="target_position_stepper", value=str(self.target_position), disabled=True)
        yield Label("Max value: ", id="max_value_label")
        yield Input(id="max_value_stepper", value=str(self.max_value), disabled=True)
        yield Label("Min value: ", id="min_value_label")
        yield Input(id="min_value_stepper", value=str(self.min_value), disabled=True)


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
        yield ScrollableContainer(
            StepperMotor(id="stepper_motor_1"), 
            StepperMotor(id="stepper_motor_2"), 
            StepperMotor(id="stepper_motor_3"), 
            id="scant")
    
    def action_toggle_dark(self) -> None:
        """An action to toggle dark mode."""
        self.dark = not self.dark

if __name__ == "__main__":
    app = Scant()
    app.run()
