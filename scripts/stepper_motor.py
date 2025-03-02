from typing import Optional, Tuple, List
from textual.widgets import Static, Button, Input, Select, Label
from textual.reactive import reactive
from settings import SettingsManager
from scan import ScanManager
from utils import get_axes, get_stepper_motor_serial_numbers, ScanState
from ticlib import TicUSB
from textual import on
from textual.app import App, ComposeResult
import re
from progress_display import ProgressDisplay
from current_position import CurrentPositionDisplay
from target_position import TargetPositionDisplay
from max_position import MaxPositionDisplay
from min_position import MinPositionDisplay
from current_limit import CurrentLimitDisplay


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
        if not self.tic or not self.initialized:
            return
        
        # If a scan is running, stop it first
        if self.scan_state != ScanState.IDLE:
            self.stop_scan()
        
        # First halt the motor where it is
        self.tic.halt_and_hold()
        
        # Set the current position as zero
        self.tic.halt_and_set_position(0)
        
        # Update our tracking variables and displays
        self.current_position = 0
        self.target_position = 0
        current_pos_display = self.query_one(CurrentPositionDisplay)
        target_pos_display = self.query_one(TargetPositionDisplay)
        current_pos_display.update_current_position(0)
        target_pos_display.update_target_position(0)
        
        # Re-enable motor movement
        self.tic.exit_safe_start()
        
        print(f"{self.id} zeroed - Current position: {self.current_position}, Target position: {self.target_position}")

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
        scanning_in_progress = self.scan_state != ScanState.IDLE
        
        # Configuration controls (disabled during scan)
        config_controls = ["axis_stepper", "serial_stepper", "current_limit_stepper", "max_speed_stepper"]
        for control_id in config_controls:
            control = self.query_one(f"#{control_id}")
            control.disabled = not self.initialized or scanning_in_progress
            if not control.disabled:
                control.add_class("enabled")
            else:
                control.remove_class("enabled")

        # Power button (disabled during scan)
        power_button = self.query_one("#power_stepper")
        power_button.label = "Off" if self.initialized else "On"
        power_button.disabled = scanning_in_progress
        power_button.add_class("enabled")
        if scanning_in_progress:
            power_button.remove_class("enabled")

        # Energize button (always enabled when ON)
        energize_button = self.query_one("#energize_stepper")
        energize_button.disabled = not self.initialized
        energize_button.label = "Deenergize" if self.energized else "Energize"
        if self.energized:
            energize_button.add_class("energized")
        else:
            energize_button.remove_class("energized")
        if not energize_button.disabled:
            energize_button.add_class("enabled")
        else:
            energize_button.remove_class("enabled")

        # Zero button (always enabled when ON)
        zero_button = self.query_one("#zero_stepper")
        zero_button.disabled = not self.initialized
        if not zero_button.disabled:
            zero_button.add_class("enabled")
        else:
            zero_button.remove_class("enabled")

        # Position inputs (disabled during scan)
        position_controls = ["divisions_stepper", "min_position_stepper", "max_position_stepper"]
        for control_id in position_controls:
            control = self.query_one(f"#{control_id}")
            control.disabled = not self.initialized or scanning_in_progress
            if not control.disabled:
                control.add_class("enabled")
            else:
                control.remove_class("enabled")

        # Scan button (enabled when ON and ENERGIZED, or when scanning is in progress)
        scan_button = self.query_one("#run_stepper")
        scan_button.disabled = not ((self.initialized and self.energized) or scanning_in_progress)
        scan_button.label = "Stop" if scanning_in_progress else "Scan"
        if not scan_button.disabled:
            scan_button.add_class("enabled")
        else:
            scan_button.remove_class("enabled")

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
                self.query_one(ProgressDisplay).update_total_divisions(event.value)
            
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
            
            # Update the title to match the selected axis
            title_label = self.query_one(f"#{self.id}_title", Label)
            title_label.update(f"{event.value} Control")
            
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
        # Add a title for the stepper motor
        yield Label(f"{self.name} Control", id=f"{self.id}_title", classes="stepper-title")
        
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
        yield Button("Scan", id="run_stepper", variant="success", disabled=True)
        
        # Position displays
        yield CurrentPositionDisplay()
        yield TargetPositionDisplay()
        yield MinPositionDisplay()
        yield MaxPositionDisplay()
        
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
        yield Static()
        
        # Add spacers to fill the grid properly
        for _ in range(4):  # Add 4 spacers to fill the last row of the 4x5 grid
            yield Static()
        
        # Now add the progress bar as the last widget, which will appear in the 6th row
        progress_bar = ProgressDisplay(id="progress_display")
        progress_bar.styles.column_span = 4  # Span all columns
        yield progress_bar
        
        # Initialize with visible progress
        self.set_timer(0.2, lambda: progress_bar.update(progress=10))

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
        progress_display = self.query_one(ProgressDisplay)
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
            progress = self.query_one(ProgressDisplay)
            progress.start_new_movement(current_pos, target_pos)
            self.scan_state = ScanState.MOVING

    def start_scan(self) -> None:
        """Start a new scan"""
        if not self.validate_scan_parameters():
            return
        
        positions = self.get_division_positions()
        if not positions:
            return
        
        # Reset scan state
        self.current_division = 0
        self.target_position = positions[0]
        
        # Initialize progress display
        progress = self.query_one(ProgressDisplay)
        progress.reset()
        progress.start_new_movement(self.current_position, self.target_position)
        
        # Start state machine
        self.scan_state = ScanState.MOVING
        
        # Update button states for scanning
        self.update_control_states()
        
        print(f"{self.id} starting scan with {len(positions)} positions")

    def stop_scan(self) -> None:
        """Stop the current scan"""
        if self._wait_timer:
            self._wait_timer.stop()
            self._wait_timer = None
        
        # Halt the motor immediately
        if self.tic and self.energized:
            self.tic.halt_and_hold()
            # Set current position as target to prevent further movement
            current_pos = self.tic.get_current_position()
            self.tic.halt_and_set_position(current_pos)
            self.target_position = current_pos
            self.tic.exit_safe_start()
            print(f"{self.id} motor halted at position {current_pos}")
        
        # Reset scan state
        self.scan_state = ScanState.IDLE
        self.current_division = 0
        
        # Reset progress display
        progress = self.query_one(ProgressDisplay)
        progress.reset()
        
        # Update displays
        current_pos_display = self.query_one(CurrentPositionDisplay)
        target_pos_display = self.query_one(TargetPositionDisplay)
        current_pos_display.update_current_position(self.current_position)
        target_pos_display.update_target_position(self.target_position)
        
        # Update button states after scan
        self.update_control_states()
        
        print(f"{self.id} scan stopped")

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
                run_button.label = "Scan"  # Always show "Scan" instead of "Re-Scan"
                run_button.variant = "success"
                run_button.disabled = not self.validate_scan_parameters()
            else:  # SCANNING or WAITING
                run_button.label = "Stop"
                run_button.variant = "warning"
                run_button.disabled = False
            
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