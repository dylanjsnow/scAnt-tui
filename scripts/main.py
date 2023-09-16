import subprocess
import time

from textual import on
from textual import log
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Button, Static, Select, Label, Input
from textual.containers import ScrollableContainer, Vertical
from textual.reactive import reactive
from ticlib import TicUSB

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

def get_target_position_buttons():
    """Return the buttons that can be used to change the target position"""
    return ["plus_10_stepper", "plus_100_stepper", "plus_1000_stepper", "minus_10_stepper", "minus_100_stepper", "minus_1000_stepper"]

def get_buttons_to_initialize():
    """Return a list of buttons that should be disabled until the stepper motor is initialized"""
    return ["energize_stepper", "deenergize_stepper", "zero_stepper"] + get_target_position_buttons()

def get_current_limits():
    """Return a list of current limits"""
    pass

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

class StepperMotor(Static):
    """A stepper motor interface"""
    axes = get_axes()
    axis = reactive("")
    serial_numbers = get_stepper_motor_serial_numbers()
    serial_number = reactive("")
    current_position = reactive(0)
    target_position = reactive(0)
    max_position = reactive(0)
    min_position = reactive(0)
    moving = reactive(False)
    energized = reactive(False)
    initialized = reactive(False)
    divisions = reactive(0) # How many divisions (between maximum and minimum position) to take photos
    tic = None # USB connection to the stepper motor

    def reset(self):
        self.axis = ""
        self.serial_number = ""
        self.current_position = 0
        self.query_one(CurrentPositionDisplay).current_position = self.current_position
        self.target_position = 0
        self.query_one(TargetPositionDisplay).current_position = self.target_position
        self.max_position = 0
        self.query_one(MaxPositionDisplay).max_position = self.max_position
        self.min_position = 0
        self.query_one(MinPositionDisplay).min_position = self.min_position
        self.moving = False

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        self.add_class("deenergized")
        self.serial_number = self.serial_numbers[int(self.id.split("_")[-1]) - 1] if len(self.serial_numbers) > 0 else ""
        self.set_interval(1 / 10.0, self.watch_current_position)
        self.set_interval(1 / 10.0, self.watch_target_position)

    def watch_current_position(self) -> None:
        if self.tic and self.energized:
            self.current_position = self.tic.get_current_position()
            self.query_one(CurrentPositionDisplay).current_position = self.current_position
            self.moving = self.tic.get_current_position() != self.tic.get_target_position()
            
        if self.moving:
            print(self.id, " current position: ", self.current_position)
            print(self.id, " target position: ", self.target_position)

    def watch_target_position(self) -> None:
        if self.tic and self.energized:
            self.tic.set_target_position(self.target_position)
            self.query_one(TargetPositionDisplay).target_position = self.target_position
            if self.target_position > self.max_position:
                self.max_position = self.target_position
                self.query_one(MaxPositionDisplay).max_position = self.max_position
            if self.target_position < self.min_position:
                self.min_position = self.target_position
                self.query_one(MinPositionDisplay).min_position = self.min_position

    def zero_stepper(self):
        if self.tic and self.energized:
            self.tic.halt_and_set_position(0)
            self.tic.exit_safe_start()
            self.current_position = 0
            self.query_one(CurrentPositionDisplay).current_position = self.current_position
            self.target_position = 0
            self.query_one(TargetPositionDisplay).target_position = self.target_position
            self.moving = False

    def update_initialized(self, event: Button.Pressed) -> None:
        self.initialized = not self.initialized
        for button in self.query(Button):
            if button.id in ["energize_stepper", "deenergize_stepper", "zero_stepper"]:
                button.disabled = not self.initialized
        for input in self.query(Input):
            if input.id in ["target_position_stepper", "max_position_stepper", "min_position_stepper"]:
                input.disabled = not self.initialized
        if self.initialized:
            self.add_class("initialized")
            self.tic = TicUSB(serial_number=self.serial_number)
        else:
            self.remove_class("initialized")
            self.remove_class("energized")
            self.remove_class("deenergized")
            self.energized = False
        for select in self.query(Select):
            if select.id in ["axis_stepper", "serial_stepper", "zero_stepper", "divisions_stepper"]:
                select.disabled = self.initialized
        for button in self.query(Button):
            if button.id in get_buttons_to_initialize():
                button.disabled = not self.initialized     

    def update_energized(self, event: Button.Pressed) -> None:
        self.remove_class("deenergized")
        self.remove_class("initialized")
        self.add_class("energized")
        self.energized = True
        self.tic.halt_and_set_position(self.current_position)
        self.tic.energize()
        self.tic.exit_safe_start()


    def update_deenergized(self, event: Button.Pressed) -> None:
        self.remove_class("energized")
        self.remove_class("initialized")
        self.add_class("deenergized")
        self.energized = False
        self.tic.deenergize()

    def update_is_moving(self) -> None:
        """Update the is moving state of the stepper motor"""
        if self.energized:
            self.moving = False
        else:
            self.moving = False

    def update_target_position(self, event: Button.Pressed) -> None:
        """Update the target position of the stepper motor"""
        button_id = event.button.id

        if button_id == "plus_10_stepper":
            self.target_position += 10
        elif button_id == "plus_100_stepper":
            self.target_position += 100
        elif button_id == "plus_1000_stepper":
            self.target_position += 1000
        elif button_id == "minus_10_stepper":
            self.target_position -= 10
        elif button_id == "minus_100_stepper":
            self.target_position -= 100
        elif button_id == "minus_1000_stepper":
            self.target_position -= 1000
        else:
            self.target_position = self.target_position
        print(self.id, " target position: ", self.target_position)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button press"""
        print(self.id, " button pressed: ", event.button.id)
        
        if event.button.id == "initialize_stepper":
            self.update_initialized(event)
        elif event.button.id == "energize_stepper":
            self.update_energized(event)
        elif event.button.id == "deenergize_stepper":
            self.update_deenergized(event)
        elif event.button.id == "zero_stepper":
            self.zero_stepper()
        elif event.button.id in get_target_position_buttons():
            self.update_target_position(event)
            
    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle an input change"""
        print(self.id, " input changed: ", event.value)
        if event.input.id == "divisions_stepper":
            self.divisions = event.value

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
        yield Button("Zero", id="zero_stepper", variant="primary", disabled=True)
        yield Button("Deenergize", id="deenergize_stepper", variant="error", disabled=True)
        yield CurrentPositionDisplay()
        yield TargetPositionDisplay()
        yield MinPositionDisplay()
        yield MaxPositionDisplay()
        yield Button("+1000", id="plus_1000_stepper", variant="primary", disabled=True)
        yield Button("+100", id="plus_100_stepper", variant="primary", disabled=True)
        yield Button("+10", id="plus_10_stepper", variant="primary", disabled=True)
        yield Button("-10", id="minus_10_stepper", variant="primary", disabled=True)
        yield Button("-100", id="minus_100_stepper", variant="primary", disabled=True)
        yield Button("-1000", id="minus_1000_stepper", variant="primary", disabled=True)
        yield Label("Divisions: ", id="photo_divisions_label")
        yield Input(placeholder="Divisions", id="divisions_stepper", disabled=True)
        yield Input(placeholder="Set max: ", id="max_position_stepper", disabled=True)
        yield Input(placeholder="Set min: ", id="min_position_stepper",  disabled=True)


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
