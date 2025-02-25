import re
import subprocess
import time
from enum import Enum
import json
import os
from pathlib import Path
from threading import Thread
from queue import Queue

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
    return ["divisions_stepper", "max_position_stepper", "min_position_stepper", "max_speed_stepper"]

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
    current_limit = reactive(2)  # Default to 174mA (code 2)
    max_speed = reactive(0)  # Add this with other reactive properties
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.settings = SettingsManager()
        
        # Create current limit options tuple
        self.current_limit_options = (
            ("0 mA (0)", "0"),
            ("1 mA (1)", "1"),
            ("174 mA (2)", "2"),
            ("343 mA (3)", "3"),
            ("495 mA (4)", "4"),
            ("634 mA (5)", "5"),
            ("762 mA (6)", "6"),
            ("880 mA (7)", "7"),
            ("990 mA (8)", "8"),
            ("1092 mA (9)", "9"),
            ("1189 mA (10)", "10"),
            ("1281 mA (11)", "11"),
            ("1368 mA (12)", "12"),
            ("1452 mA (13)", "13"),
            ("1532 mA (14)", "14"),
            ("1611 mA (15)", "15"),
            ("1687 mA (16)", "16"),
            ("1762 mA (17)", "17"),
            ("1835 mA (18)", "18"),
            ("1909 mA (19)", "19"),
            ("1982 mA (20)", "20"),
            ("2056 mA (21)", "21"),
            ("2131 mA (22)", "22"),
            ("2207 mA (23)", "23"),
            ("2285 mA (24)", "24"),
            ("2366 mA (25)", "25"),
            ("2451 mA (26)", "26"),
            ("2540 mA (27)", "27"),
            ("2634 mA (28)", "28"),
            ("2734 mA (29)", "29"),
            ("2843 mA (30)", "30"),
            ("2962 mA (31)", "31"),
            ("3093 mA (32)", "32"),
        )

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
        
        # Load saved settings into inputs
        stepper_num = self.id.split("_")[-1]
        print(f"\nLoading saved settings for {self.id}:")
        divisions = self.settings.get_setting(stepper_num, "divisions")
        min_pos = self.settings.get_setting(stepper_num, "min_position")
        max_pos = self.settings.get_setting(stepper_num, "max_position")
        current_limit = self.settings.get_setting(stepper_num, "current_limit") or "2"  # Default to 2 if empty
        saved_axis = self.settings.get_setting(stepper_num, "axis")
        saved_serial = self.settings.get_setting(stepper_num, "serial")
        max_speed = self.settings.get_setting(stepper_num, "max_speed") or "1000"  # Default to 1000 if empty
        
        print(f"Setting input values for {self.id}:")
        print(f"  divisions: {divisions}")
        print(f"  min_position: {min_pos}")
        print(f"  max_position: {max_pos}")
        print(f"  current_limit: {current_limit}")
        print(f"  axis: {saved_axis}")
        print(f"  serial: {saved_serial}")
        
        # Set default values if saved values are empty
        if not saved_axis and len(self.axes) > 0:
            saved_axis = self.axes[int(stepper_num) - 1]
        if not saved_serial and len(self.serial_numbers) > 0:
            saved_serial = self.serial_numbers[int(stepper_num) - 1]
            
        # Set the values to the widgets
        self.query_one("#divisions_stepper").value = divisions
        self.query_one("#min_position_stepper").value = min_pos
        self.query_one("#max_position_stepper").value = max_pos
        if current_limit in [opt[1] for opt in self.current_limit_options]:
            self.query_one("#current_limit_stepper").value = current_limit
        if saved_axis in self.axes:
            self.query_one("#axis_stepper").value = saved_axis
        if saved_serial in self.serial_numbers:
            self.query_one("#serial_stepper").value = saved_serial
        self.query_one("#max_speed_stepper").value = max_speed
            
        # Set up intervals
        self.set_interval(1 / 10.0, self.watch_current_position)
        self.set_interval(1 / 10.0, self.watch_target_position)
        self.set_interval(0.1, self.update_scan_state)
        self.set_timer(0.1, self.update_button_state)
        
        # Initialize control states
        self.update_control_states()

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

    def is_position_reached(self) -> bool:
        """Check if current position is within tolerance of target"""
        if not self.energized or not self.tic:
            return False
        
        current_pos = int(float(self.current_position))
        target_pos = int(float(self.target_position))
        tolerance = abs(int(target_pos * self.POSITION_TOLERANCE))
        return abs(current_pos - target_pos) <= tolerance

    def is_position_reached_exact(self) -> bool:
        """Check if current position exactly matches target"""
        if not self.energized or not self.tic:
            return False
        
        current_pos = int(float(self.current_position))
        target_pos = int(float(self.target_position))
        return current_pos == target_pos

    def zero_stepper(self):
        """Zero the stepper motor using Tic commands"""
        if not self.tic or not self.energized:
            return
        
        # If a scan is running, stop it first
        if self.scan_state != ScanState.IDLE:
            self.stop_scan()
        
        # First halt the motor where it is
        self.tic.halt_and_hold()
        
        # Set the current position as zero
        self.tic.halt_and_set_position(0)
        
        # Update our tracking variables
        self.current_position = 0
        self.target_position = 0
        self.query_one(CurrentPositionDisplay).current_position = 0
        self.query_one(TargetPositionDisplay).target_position = 0
        
        # Re-enable motor movement
        self.tic.exit_safe_start()

    def update_initialized(self, event: Button.Pressed) -> None:
        """Handle power button press"""
        self.initialized = not self.initialized
        if self.initialized:
            self.add_class("initialized")
            self.tic = TicUSB(serial_number=self.serial_number)
        else:
            # If turning off, ensure motor is deenergized
            if self.energized:
                self.update_energized(event)
            self.remove_class("initialized")
            self.remove_class("energized")
            self.tic = None
            
        self.update_control_states()

    def update_energized(self, event: Button.Pressed) -> None:
        """Handle energize button press"""
        if self.energized:
            # Deenergize
            self.remove_class("energized")
            self.energized = False
            self.tic.deenergize()
        else:
            # Energize
            self.add_class("energized")
            self.energized = True
            self.tic.halt_and_set_position(self.current_position)
            
            # Set the current limit when energizing
            if self.current_limit:
                print(f"{self.id} current limit set to: {self.current_limit}")
                self.tic.set_current_limit(int(self.current_limit))
                
            self.tic.energize()
            self.tic.exit_safe_start()
            
        self.update_control_states()

    def update_control_states(self) -> None:
        """Update all control states based on current motor state"""
        # Configuration controls (only enabled when OFF)
        config_controls = ["axis_stepper", "serial_stepper", "current_limit_stepper", "max_speed_stepper"]
        for control_id in config_controls:
            control = self.query_one(f"#{control_id}")
            control.disabled = self.initialized
            if not control.disabled:
                control.add_class("enabled")
            else:
                control.remove_class("enabled")

        # Power button
        power_button = self.query_one("#power_stepper")
        power_button.label = "Off" if self.initialized else "On"
        power_button.add_class("enabled")

        # Energize button
        energize_button = self.query_one("#energize_stepper")
        energize_button.disabled = not self.initialized
        energize_button.label = "Deenergize" if self.energized else "Energize"
        if not energize_button.disabled:
            energize_button.add_class("enabled")
        else:
            energize_button.remove_class("enabled")

        # Operation controls (enabled when ON)
        operation_controls = ["zero_stepper", "run_stepper", "divisions_stepper",
                            "min_position_stepper", "max_position_stepper"]
        
        for control_id in operation_controls:
            control = self.query_one(f"#{control_id}")
            # Only enable if initialized AND (not energized OR scan button)
            control.disabled = not self.initialized or (self.energized and control_id != "run_stepper")
            if not control.disabled:
                control.add_class("enabled")
            else:
                control.remove_class("enabled")

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
        
        if event.button.id == "power_stepper":
            self.update_initialized(event)
        elif event.button.id == "energize_stepper":
            self.update_energized(event)
        elif event.button.id == "zero_stepper":
            self.zero_stepper()
        elif event.button.id == "run_stepper":
            if self.scan_state == ScanState.IDLE:
                self.start_scan()
            else:
                self.stop_scan()
            
    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle an input change"""
        stepper_num = self.id.split("_")[-1]
        
        if event.input.id == "divisions_stepper":
            self.divisions = event.value
            self.settings.queue_save(stepper_num, "divisions", event.value)
            if event.value and event.value.isdigit():
                self.query_one(DivisionDisplay).update_total_divisions(event.value)
            
        elif event.input.id == "max_position_stepper":
            numbers = re.findall(r"[-+]?(?:\d*\.*\d+)", event.value)
            value = numbers[0] if numbers else ""
            self.max_position = value
            self.settings.queue_save(stepper_num, "max_position", value)
            self.query_one(MaxPositionDisplay).max_position = self.max_position
            
        elif event.input.id == "min_position_stepper":
            numbers = re.findall(r"[-+]?(?:\d*\.*\d+)", event.value)
            value = numbers[0] if numbers else ""
            self.min_position = value
            self.settings.queue_save(stepper_num, "min_position", value)
            self.query_one(MinPositionDisplay).min_position = self.min_position
        
        elif event.input.id == "max_speed_stepper":
            try:
                # Convert to float to handle decimal inputs
                speed = float(event.value)
                
                # Validate speed range (0.005 to 50000 steps/s)
                min_speed = 0.005  # 1/200 steps per second
                max_speed = 50000
                
                if speed < min_speed:
                    speed = min_speed
                elif speed > max_speed:
                    speed = max_speed
                
                # Convert to integer for the Tic controller
                speed_steps = int(speed * 10000)  # Tic expects speed in units of steps * 10000
                
                # Update the motor if connected
                if self.tic and self.energized:
                    self.tic.set_max_speed(speed_steps)
                    self.tic.exit_safe_start()
                
                # Update display and save setting
                self.max_speed = speed
                self.settings.queue_save(stepper_num, "max_speed", str(speed))
                
            except (ValueError, TypeError):
                # Invalid input - reset to previous value
                event.input.value = str(self.max_speed)
        
        # Update Run button state
        run_button = self.query_one("#run_stepper")
        run_button.disabled = not self.validate_scan_parameters()

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle a select change"""
        print(self.id, " select changed to: ", event.value)
        stepper_num = self.id.split("_")[-1]
        
        if event.select.id == "axis_stepper":
            self.axis = event.value
            print(self.id, " axis: ", self.axis)
            self.settings.queue_save(stepper_num, "axis", event.value)
            
        elif event.select.id == "serial_stepper":
            self.serial_number = event.value
            print(self.id, " serial number: ", self.serial_number)
            self.settings.queue_save(stepper_num, "serial", event.value)
            
        elif event.select.id == "current_limit_stepper":
            self.current_limit = event.value
            # Get the mA value from the options tuple for display
            current_ma = next(opt[0] for opt in self.current_limit_options if opt[1] == event.value)
            print(f"{self.id} current limit set to: {current_ma}")
            self.settings.queue_save(stepper_num, "current_limit", event.value)
            
            # Update the motor if it's connected and energized
            if self.tic and self.energized:
                self.tic.set_current_limit(int(event.value))
                self.tic.exit_safe_start()

    def compose(self) -> ComposeResult:
        """Create child widgets for the stepper motor"""
        # Configuration controls - only enabled when OFF
        yield Select(
            options=((axis, axis) for axis in self.axes), 
            id="axis_stepper",
            value=self.axes[int(self.id.split("_")[-1]) - 1],
            allow_blank=False,
            prompt="Select axis",
            tooltip="Choose the movement axis for this stepper motor"
        )
        yield Select(
            options=((serial, serial) for serial in self.serial_numbers),
            id="serial_stepper", 
            value=self.serial_numbers[int(self.id.split("_")[-1]) - 1] if len(self.serial_numbers) > 0 else "",
            allow_blank=False,
            prompt="Select device",
            tooltip="Choose the serial number of the Tic stepper motor controller"
        )
        yield Select(
            options=self.current_limit_options,
            id="current_limit_stepper",
            value="2",
            allow_blank=False,
            prompt="Select current limit",
            tooltip="Set the maximum current for the stepper motor coils"
        )
        yield Input(
            placeholder="Maximum speed (steps/s)",
            id="max_speed_stepper",
            value="1000",
            tooltip="Set the maximum speed in steps per second (0.005 to 50000 steps/s)",
            type="number"
        )
        
        # Main control buttons
        yield Button("On", id="power_stepper", variant="default")
        yield Button("Energize", id="energize_stepper", variant="default", disabled=True)
        yield Button("Zero", id="zero_stepper", variant="primary", disabled=True)
        
        # Position displays
        yield CurrentPositionDisplay()
        yield TargetPositionDisplay()
        yield MinPositionDisplay()
        yield MaxPositionDisplay()
        
        # Scan controls - enabled when ON
        yield Button("Scan", id="run_stepper", variant="success", disabled=True)
        yield Input(
            placeholder="Number of positions to scan",
            id="divisions_stepper",
            disabled=True,
            tooltip="Enter the number of evenly-spaced positions to stop at during the scan",
            type="integer"
        )
        yield Input(
            placeholder="Minimum position (steps)",
            id="min_position_stepper",
            disabled=True, 
            tooltip="Enter the minimum motor position in steps (-2,147,483,648 to 2,147,483,647)",
            type="integer"
        )
        yield Input(
            placeholder="Maximum position (steps)",
            id="max_position_stepper",
            disabled=True,
            tooltip="Enter the maximum motor position in steps (-2,147,483,648 to 2,147,483,647)",
            type="integer"
        )
        
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

    def start_scan(self) -> None:
        """Start the scanning sequence"""
        if not self.validate_scan_parameters():
            return
            
        # Stop any active zero timer
        if hasattr(self, '_zero_timer') and self._zero_timer:
            self._zero_timer.stop()
            self._zero_timer = None
            
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
        # Stop any active timers
        if hasattr(self, '_zero_timer') and self._zero_timer:
            self._zero_timer.stop()
            self._zero_timer = None
            
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

class SettingsManager:
    """Manages saving and loading of stepper motor settings"""
    
    def __init__(self):
        self.settings_file = Path(__file__).parent / "settings.json"
        self.save_queue = Queue()
        print(f"Initializing SettingsManager with settings file: {self.settings_file}")
        self.settings = self._load_settings()
        
        # Start background save thread
        self.save_thread = Thread(target=self._background_save, daemon=True)
        self.save_thread.start()

    def _get_default_settings(self) -> dict:
        """Get default settings using stepper_1's configuration as template"""
        return {
            "stepper_1": {
                "divisions": "",
                "min_position": "",
                "max_position": "",
                "current_limit": "2",
                "axis": "Forward",  # Default to first axis
                "serial": "",  # Will be set by first available serial
                "max_speed": "1000"
            }
        }

    def _load_settings(self) -> dict:
        """Load settings from file or return defaults"""
        try:
            if self.settings_file.exists():
                print(f"Loading settings from {self.settings_file}")
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    
                    # Get defaults from stepper_1 or create new defaults
                    defaults = (settings.get("stepper_1", {}) if "stepper_1" in settings 
                              else self._get_default_settings()["stepper_1"])
                    
                    # Ensure all steppers exist with proper defaults
                    for stepper in ["1", "2", "3"]:
                        stepper_key = f"stepper_{stepper}"
                        if stepper_key not in settings:
                            settings[stepper_key] = {}
                            
                        # Copy defaults for each setting if not present
                        for key, default_value in defaults.items():
                            if key not in settings[stepper_key] or not settings[stepper_key][key]:
                                if key == "axis":
                                    # Special handling for axis - use corresponding default axis
                                    axes = get_axes()
                                    axis_index = int(stepper) - 1
                                    settings[stepper_key][key] = axes[axis_index] if axis_index < len(axes) else default_value
                                else:
                                    settings[stepper_key][key] = default_value
                                    
                    print(f"Loaded settings: {json.dumps(settings, indent=2)}")
                    return settings
                    
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading settings: {e}")
        
        # If no valid settings file exists, create default settings
        print("Using default settings")
        defaults = self._get_default_settings()["stepper_1"]
        settings = {}
        
        # Create settings for each stepper using defaults
        for stepper in ["1", "2", "3"]:
            stepper_key = f"stepper_{stepper}"
            settings[stepper_key] = defaults.copy()
            # Set appropriate axis for each stepper
            axes = get_axes()
            axis_index = int(stepper) - 1
            if axis_index < len(axes):
                settings[stepper_key]["axis"] = axes[axis_index]
                
        return settings

    def queue_save(self, stepper_id: str, setting_type: str, value: str):
        """Queue a settings save operation"""
        stepper_key = f"stepper_{stepper_id}"
        print(f"Queueing save for {stepper_key} {setting_type}: {value}")
        
        # Create a deep copy of current settings
        settings_copy = json.loads(json.dumps(self.settings))
        
        # Update the specific setting
        if stepper_key not in settings_copy:
            # If stepper doesn't exist, create it with defaults from stepper_1
            settings_copy[stepper_key] = json.loads(json.dumps(
                settings_copy.get("stepper_1", self._get_default_settings()["stepper_1"])
            ))
        
        settings_copy[stepper_key][setting_type] = value
        
        # Update internal settings and queue the save
        self.settings = settings_copy
        self.save_queue.put(settings_copy)
        
        print("Current settings state:")
        print(json.dumps(self.settings, indent=2))

    def get_setting(self, stepper_id: str, setting_type: str) -> str:
        """Get a setting value"""
        stepper_key = f"stepper_{stepper_id}"
        
        # If the stepper or setting doesn't exist, get default from stepper_1
        if stepper_key not in self.settings or setting_type not in self.settings[stepper_key]:
            default_value = ""
            if "stepper_1" in self.settings and setting_type in self.settings["stepper_1"]:
                default_value = self.settings["stepper_1"][setting_type]
            elif setting_type == "axis":
                # Special handling for axis - use corresponding default axis
                axes = get_axes()
                axis_index = int(stepper_id) - 1
                default_value = axes[axis_index] if axis_index < len(axes) else axes[0]
            
            return default_value
            
        value = self.settings[stepper_key][setting_type]
        print(f"Getting setting for {stepper_key} {setting_type}: {value}")
        return value

    def _background_save(self):
        """Background thread for saving settings atomically"""
        while True:
            try:
                # Wait for new settings to save
                settings = self.save_queue.get()
                print(f"Saving settings to {self.settings_file}:")
                print(json.dumps(settings, indent=2))
                
                # Write to temporary file first
                temp_file = self.settings_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(settings, f, indent=4)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure write is complete
                    
                # Rename temp file to actual file (atomic operation)
                temp_file.replace(self.settings_file)
                    
            except Exception as e:
                print(f"Error saving settings: {e}")
            
            time.sleep(0.1)  # Prevent excessive saves

class ScanManager(Static):
    """Manages coordinated scanning across all stepper motors"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stepper_motors = []
        self.scanning = False
        
    def on_mount(self) -> None:
        """Get references to stepper motors after mount"""
        # Wait briefly to ensure steppers are mounted
        def get_steppers():
            self.stepper_motors = [
                self.app.query_one("#stepper_motor_1"),
                self.app.query_one("#stepper_motor_2"), 
                self.app.query_one("#stepper_motor_3")
            ]
            
        self.set_timer(0.1, get_steppers)
        
    def compose(self) -> ComposeResult:
        """Create child widgets for scan management"""
        yield Button("Start Full Scan", id="start_full_scan", variant="success")
        yield Button("Stop All", id="stop_all_scan", variant="error")
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        if event.button.id == "start_full_scan":
            self.start_full_scan()
        elif event.button.id == "stop_all_scan":
            self.stop_all_scans()
            
    def start_full_scan(self) -> None:
        """Start a coordinated scan across all motors"""
        if not self.stepper_motors:
            return
            
        # Check if all motors are ready
        ready_motors = []
        for motor in self.stepper_motors:
            if motor.validate_scan_parameters():
                ready_motors.append(motor)
                
        if not ready_motors:
            return
            
        # Start scan on all ready motors
        self.scanning = True
        for motor in ready_motors:
            motor.start_scan()
            
        # Update button states
        start_button = self.query_one("#start_full_scan")
        start_button.disabled = True
        stop_button = self.query_one("#stop_all_scan") 
        stop_button.disabled = False
        
        # Set up monitoring of scan completion
        self.set_interval(0.1, self.check_scan_completion)
        
    def stop_all_scans(self) -> None:
        """Stop scanning on all motors"""
        if not self.stepper_motors:
            return
            
        self.scanning = False
        for motor in self.stepper_motors:
            if motor.scan_state != ScanState.IDLE:
                motor.stop_scan()
                
        # Update button states
        start_button = self.query_one("#start_full_scan")
        start_button.disabled = False
        stop_button = self.query_one("#stop_all_scan")
        stop_button.disabled = True
        
    def check_scan_completion(self) -> bool:
        """Check if all motors have completed scanning"""
        if not self.scanning:
            return False
            
        all_complete = True
        for motor in self.stepper_motors:
            if motor.scan_state != ScanState.IDLE:
                all_complete = False
                break
                
        if all_complete:
            self.scanning = False
            # Update button states
            start_button = self.query_one("#start_full_scan")
            start_button.disabled = False
            stop_button = self.query_one("#stop_all_scan")
            stop_button.disabled = True
            return False  # Stop the interval
            
        return True  # Continue checking

class Scant(App):
    """The main application."""
    CSS_PATH = "main.tcss"

    def compose(self) -> ComposeResult:
        """Create child widgets for the app"""
        yield Header()
        yield Footer()
        yield ScanManager()
        yield ScrollableContainer(
            StepperMotor(id="stepper_motor_1"), 
            StepperMotor(id="stepper_motor_2"), 
            StepperMotor(id="stepper_motor_3"), 
            id="scant")

if __name__ == "__main__":
    app = Scant()
    app.run()
