import re
import subprocess
import time
from enum import Enum

from textual import on
from textual import log
from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Button, Static, Select, Label, Input, ProgressBar
from textual.containers import ScrollableContainer, Vertical
from textual.reactive import reactive
from ticlib import TicUSB
from textual.worker import Worker, get_current_worker
from textual.timer import Timer
from rich.progress import Progress

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
    return ["Forward", "Tilt", "Yaw"] # A.k.a Forward, Pitch, Heading (planes) or Z direction, X, Y (camera calibration computer vision)

def get_buttons_to_initialize():
    """Return a list of buttons that should be disabled until the stepper motor is initialized"""
    return ["run_stepper"]

def get_inputs_to_initialize():
    """Return a list of inputs that should be disabled until the stepper motor is initialized"""
    return ["divisions_stepper", "max_position_stepper", "min_position_stepper"]

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

class DivisionDisplay(ProgressBar):
    """A widget to display division and position progress using a progress bar"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(
            total=100,  # Use percentage for total
            show_bar=True,
            show_percentage=True,
            show_eta=True,
            name="division_display",
            id="division_display"
        )
        self.total_divisions = 0
        self.current_division = 0
        self.current_position = 0
        self.target_position = 0
        self.start_position = 0  # Track start position of current movement
        self.position_tolerance = 0.05

    def update_progress(self, current_division: int, total_divisions: int, 
                       current_pos: float, target_pos: float, wait_time: float = 2.0) -> None:
        """Update progress based on both division and position progress"""
        self.total_divisions = max(1, total_divisions)
        self.current_division = current_division
        self.current_position = float(current_pos)
        self.target_position = float(target_pos)
        
        # Base progress from completed divisions
        division_progress = (self.current_division / self.total_divisions) * 100
        
        # Calculate progress within current division
        if self.current_division < self.total_divisions:
            # Calculate position progress as percentage of total movement
            total_movement = abs(self.target_position - self.start_position)
            if total_movement > 0:
                remaining_movement = abs(self.target_position - self.current_position)
                position_progress = ((total_movement - remaining_movement) / total_movement)
            else:
                position_progress = 1.0
                
            # Each division contributes an equal percentage to total progress
            division_contribution = 100.0 / self.total_divisions
            current_division_progress = position_progress * division_contribution
            
            # Combine base progress with current division progress
            total_progress = division_progress + current_division_progress
        else:
            total_progress = 100.0
            
        # Debug output
        print(f"Progress: {total_progress:.1f}% (Division {self.current_division}/{self.total_divisions}, "
              f"Position: {self.current_position:.1f}/{self.target_position:.1f})")
        
        self.update(progress=min(100, max(0, total_progress)))

    def start_new_movement(self, start_pos: float, target_pos: float) -> None:
        """Called when starting movement to a new position"""
        self.start_position = float(start_pos)
        self.target_position = float(target_pos)

    def update_total_divisions(self, divisions: str) -> None:
        """Update the total number of divisions"""
        if divisions and divisions.isdigit():
            self.total_divisions = int(divisions)
        else:
            self.total_divisions = 0

    def reset(self) -> None:
        """Reset the progress tracking"""
        self.current_division = 0
        self.start_position = 0
        self.update(progress=0)

class ScanState(Enum):
    """States for the scanning process"""
    IDLE = "idle"
    MOVING = "moving" 
    WAITING = "waiting"

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
    scanning = reactive(False)  # Track if we're currently scanning
    scan_state = reactive(ScanState.IDLE)
    current_division = reactive(0)
    POSITION_TOLERANCE = 0.05  # 5% tolerance for position matching
    DIVISION_WAIT_TIME = 2.0  # Seconds to wait at each division
    _wait_timer = None  # Store reference to active timer

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
        # Add interval for scan state machine
        self.set_interval(0.1, self.update_scan_state)
        # Defer button state update to allow widgets to mount
        self.set_timer(0.1, self.update_button_state)

    def watch_current_position(self) -> None:
        if self.tic and self.energized:
            self.current_position = self.tic.get_current_position()
            self.query_one(CurrentPositionDisplay).current_position = self.current_position
            self.moving = self.tic.get_current_position() != self.tic.get_target_position()
            
        if self.moving:
            print(self.id, " current position: ", self.current_position)
            print(self.id, " target position: ", self.target_position)

    def watch_target_position(self) -> None:
        """Watch for target position changes and update motor"""
        if self.tic and self.energized:
            # Convert target position to integer before sending to motor
            target_pos = int(float(self.target_position))
            self.tic.set_target_position(target_pos)
            self.query_one(TargetPositionDisplay).target_position = self.target_position
            
            try:
                max_pos = float(self.max_position) if self.max_position else 0
                min_pos = float(self.min_position) if self.min_position else 0
                
                # Update max position if needed
                if self.target_position > max_pos and \
                    len(re.findall(r"[-+]?(?:\d*\.*\d+)", str(self.query_one(MaxPositionDisplay).max_position))) <= 0:
                    self.max_position = self.target_position
                    self.query_one(MaxPositionDisplay).max_position = self.max_position
                
                # Only set the min position if no user Input Min Position has been set in the GUI
                if self.target_position < min_pos and \
                    len(re.findall(r"[-+]?(?:\d*\.*\d+)", str(self.query_one(MinPositionDisplay).min_position))) <= 0:
                    self.min_position = self.target_position
                    self.query_one(MinPositionDisplay).min_position = self.min_position
            except (ValueError, TypeError):
                # If conversion fails, just continue without updating min/max
                pass

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
        for input in self.query(Input):
            if input.id in get_inputs_to_initialize():
                input.disabled = not self.initialized       

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
        new_target_position = int(float(self.target_position))
        self.target_position = new_target_position
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
        elif event.button.id == "run_stepper":
            if self.scan_state == ScanState.IDLE:
                self.start_scan()
            else:
                self.stop_scan()
        elif event.button.id in get_target_position_buttons():
            self.update_target_position(event)
            
    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle an input change"""
        if event.input.id == "divisions_stepper":
            # Store the value even if empty
            self.divisions = event.value
            # Only update progress if it's a valid number
            if event.value and event.value.isdigit():
                self.query_one(DivisionDisplay).update_total_divisions(event.value)
            print(self.id, " divisions: ", self.divisions)
            
        elif event.input.id == "max_position_stepper":
            # Extract number if present, otherwise store empty string
            numbers = re.findall(r"[-+]?(?:\d*\.*\d+)", event.value)
            self.max_position = numbers[0] if numbers else ""
            self.query_one(MaxPositionDisplay).max_position = self.max_position
            print(self.id, " max position: ", self.max_position)
            
        elif event.input.id == "min_position_stepper":
            # Extract number if present, otherwise store empty string
            numbers = re.findall(r"[-+]?(?:\d*\.*\d+)", event.value)
            self.min_position = numbers[0] if numbers else ""
            self.query_one(MinPositionDisplay).min_position = self.min_position
            print(self.id, " min position: ", self.min_position)
        
        # Always update Run button state after any input change
        run_button = self.query_one("#run_stepper")
        run_button.disabled = not self.validate_scan_parameters()

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
        yield Select(options=((axis, axis) for axis in self.axes), id="axis_stepper", value=self.axes[int(self.id.split("_")[-1]) - 1], allow_blank=False)
        yield Select(options=((serial, serial) for serial in self.serial_numbers), id="serial_stepper", value=self.serial_numbers[int(self.id.split("_")[-1]) - 1] if len(self.serial_numbers) > 0 else "", allow_blank=False)
        yield Static()
        yield Static()
        yield Button("Initialize", id="initialize_stepper", variant="default")
        yield Button("Energize", id="energize_stepper", variant="default", disabled=True)
        yield Button("Zero", id="zero_stepper", variant="primary", disabled=True)
        yield Button("Deenergize", id="deenergize_stepper", variant="error", disabled=True)
        yield CurrentPositionDisplay()
        yield TargetPositionDisplay()
        yield MinPositionDisplay()
        yield MaxPositionDisplay()
        yield Button("Scan", id="run_stepper", variant="success", disabled=True)
        yield Input(placeholder="Divisions: ", id="divisions_stepper", disabled=True)
        yield Input(placeholder="Set min: ", id="min_position_stepper", disabled=True)
        yield Input(placeholder="Set max: ", id="max_position_stepper", disabled=True)
        yield DivisionDisplay(id="division_display")

    def get_division_positions(self) -> list[int]:
        """Calculate all positions to stop at during scan, returning integer positions"""
        try:
            min_pos = int(float(self.min_position))
            max_pos = int(float(self.max_position))
            div_count = int(self.divisions)
            if div_count < 2:
                return [min_pos, max_pos]
            
            # Calculate step size, rounding to nearest integer
            step = int((max_pos - min_pos) / (div_count - 1))
            return [min_pos + (i * step) for i in range(div_count)]
        except (ValueError, TypeError):
            return []

    def is_position_reached(self) -> bool:
        """Check if current position is within tolerance of target"""
        if not self.energized or not self.tic:
            return False
        
        current_pos = int(float(self.current_position))
        target_pos = int(float(self.target_position))
        tolerance = abs(int(target_pos * self.POSITION_TOLERANCE))
        return abs(current_pos - target_pos) <= tolerance

    def finish_waiting(self) -> None:
        """Called after waiting at a position"""
        if self.scan_state != ScanState.WAITING:
            return
            
        positions = self.get_division_positions()
        self.current_division += 1
        
        if self.current_division >= len(positions):
            self.stop_scan()
        else:
            # Start new movement
            current_pos = self.current_position
            target_pos = positions[self.current_division]
            self.target_position = target_pos
            
            # Update progress tracking
            progress = self.query_one(DivisionDisplay)
            progress.start_new_movement(current_pos, target_pos)
            self.scan_state = ScanState.MOVING

    def update_scan_state(self) -> None:
        """Update the scanning state machine"""
        if self.scan_state == ScanState.IDLE:
            return

        positions = self.get_division_positions()
        if not positions:
            self.scan_state = ScanState.IDLE
            return

        # Update progress display
        progress_display = self.query_one(DivisionDisplay)
        progress_display.update_progress(
            self.current_division,
            len(positions),
            self.current_position,
            self.target_position,
            wait_time=self.DIVISION_WAIT_TIME
        )

        if self.scan_state == ScanState.MOVING:
            if self.is_position_reached():
                self.scan_state = ScanState.WAITING
                self._wait_timer = self.set_timer(self.DIVISION_WAIT_TIME, self.finish_waiting)
        elif self.scan_state == ScanState.WAITING:
            # Waiting is handled by finish_waiting callback
            pass

    def start_scan(self) -> None:
        """Start the scanning sequence"""
        if not self.validate_scan_parameters():
            return
            
        positions = self.get_division_positions()
        if not positions:
            return
            
        # Initialize scan
        self.current_division = 0  # Reset division counter when starting new scan
        current_pos = self.current_position
        target_pos = positions[0]
        self.target_position = target_pos
        
        # Reset progress display with initial movement info
        progress = self.query_one(DivisionDisplay)
        progress.start_new_movement(current_pos, target_pos)
        progress.update_progress(0, len(positions), current_pos, target_pos)
        
        # Start state machine
        self.scan_state = ScanState.MOVING

    def stop_scan(self) -> None:
        """Stop the scanning sequence"""
        # Stop any active wait timer
        if self._wait_timer:
            self._wait_timer.stop()
            self._wait_timer = None
        
        # Halt the motor at current position
        if self.tic and self.energized:
            current_pos = self.tic.get_current_position()
            self.tic.halt_and_set_position(current_pos)
            self.tic.exit_safe_start()
            self.target_position = current_pos
            
        self.scan_state = ScanState.IDLE
        # Don't reset current_division here to allow "Done" state to show
        progress = self.query_one(DivisionDisplay)
        positions = self.get_division_positions()
        total_divisions = len(positions) if positions else 0
        progress.update_progress(
            self.current_division, 
            total_divisions,
            self.current_position, 
            self.target_position
        )

    def update_button_state(self) -> None:
        """Update run button state after widgets are mounted"""
        try:
            run_button = self.query_one("#run_stepper")
            run_button.disabled = not self.validate_scan_parameters()
        except:
            # Button might not be mounted yet, that's ok
            pass

    def watch_scan_state(self) -> None:
        """Handle scan state changes"""
        try:
            run_button = self.query_one("#run_stepper")
            
            # Update button label and style based on scan state
            if self.scan_state == ScanState.IDLE:
                if self.current_division > 0:  # Scan completed
                    run_button.label = "Done/ Re-Scan"
                    run_button.variant = "success"
                else:  # Ready to start
                    run_button.label = "Scan"
                    run_button.variant = "success"
                # Only enable if parameters are valid
                run_button.disabled = not self.validate_scan_parameters()
            
            elif self.scan_state == ScanState.MOVING:
                run_button.label = "Scanning"
                run_button.variant = "warning"
                run_button.disabled = False  # Always enable stop
            
            elif self.scan_state == ScanState.WAITING:
                run_button.label = "Waiting"
                run_button.variant = "warning"
                run_button.disabled = False  # Always enable stop
            
        except:
            # Button might not be mounted yet, that's ok
            pass

    def validate_scan_parameters(self) -> bool:
        """Check if all parameters are valid for scanning"""
        try:
            # Check if values exist and are numeric
            if not self.divisions or not self.divisions.strip():
                return False
            if not self.min_position or not str(self.min_position).strip():
                return False
            if not self.max_position or not str(self.max_position).strip():
                return False
                
            min_pos = float(self.min_position)
            max_pos = float(self.max_position)
            divisions = int(self.divisions)
            
            return (
                self.energized and 
                self.initialized and 
                divisions > 0 and 
                max_pos > min_pos
            )
        except (ValueError, TypeError, AttributeError):
            return False

    def on_unmount(self) -> None:
        """Clean up when widget is removed"""
        # Stop any active timer
        if self._wait_timer:
            self._wait_timer.stop()
            self._wait_timer = None

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
