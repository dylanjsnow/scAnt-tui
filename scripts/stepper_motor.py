from textual.widgets import Static, Button, Input, Select, Label
from textual.reactive import reactive
from utils import get_axes, get_stepper_motor_serial_numbers, ScanState, CameraMessage, StepperMessage, StepperStatus
from ticlib import TicUSB
from textual import on
from textual.app import ComposeResult
import re
from progress_display import ProgressDisplay
from current_position import CurrentPositionDisplay
from target_position import TargetPositionDisplay
from max_position import MaxPositionDisplay
from min_position import MinPositionDisplay
import logging
from multiprocessing import Queue
import asyncio
import queue
from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional

# Create logger for this module
logger = logging.getLogger(__name__)



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
    scanning = reactive(False)  # Track if we're currently scanning
    scan_state = reactive(ScanState.IDLE)
    current_division = reactive(0)
    POSITION_TOLERANCE = 0.05  # 5% tolerance for position matching
    DIVISION_WAIT_TIME = 2.0  # Seconds to wait at each division
    _wait_timer = None  # Store reference to active timer
    current_limit = reactive(2)  # Default to 174mA (code 2)
    max_speed = reactive(0)  # Add this with other reactive properties
    position_queue = reactive(None)  # Added for position queue
    stepper_num = reactive(1)  # Added for stepper number
    camera_photo_queue = reactive(None)  # Added for camera photo queue
    scan_manager_queue = reactive(None)  # Added for scan manager queue
    
    def __init__(self, settings_manager, position_queue: Queue, camera_photo_queue: Queue, 
                 scan_manager_queue: Queue, stepper_num: int = 1, *args, **kwargs):
        """Initialize stepper motor with settings manager and queues."""
        super().__init__(*args, **kwargs)
        
        self.settings_manager = settings_manager
        self.position_queue = position_queue
        self.camera_photo_queue = camera_photo_queue
        self.stepper_num = stepper_num
        self.scan_manager_queue = scan_manager_queue
        
        # Initialize with empty lists if no devices found
        self.axes = get_axes() or ["Yaw", "Tilt", "Forward"]
        self.serial_numbers = get_stepper_motor_serial_numbers() or ["00000000"]
        
        # Initialize tic to None - will be set when motor is connected
        self.tic = None
        
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
        
        logger.info(f"Initialized StepperMotor {self.id} with stepper_num {self.stepper_num}")

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
        logger.debug(f"Starting on_mount for {self.id}")
        
        self.add_class("deenergized")
        
        # Load saved settings first
        logger.info(f"Loading saved settings for stepper_{self.stepper_num}:")
        
        try:
            # Load all settings with proper defaults
            self.divisions = self.settings_manager.get_setting(self.stepper_num, "divisions") or "0"
            self.min_position = self.settings_manager.get_setting(self.stepper_num, "min_position") or "0"
            self.max_position = self.settings_manager.get_setting(self.stepper_num, "max_position") or "0"
            self.current_limit = self.settings_manager.get_setting(self.stepper_num, "current_limit") or "2"
            self.max_speed = self.settings_manager.get_setting(self.stepper_num, "max_speed") or "1000"
            
            # Load axis and serial settings
            saved_axis = self.settings_manager.get_setting(self.stepper_num, "axis")
            if saved_axis in self.axes:
                self.axis = saved_axis
                self.saved_axis = saved_axis
            else:
                default_axis = self.axes[int(self.stepper_num) - 1] if int(self.stepper_num) <= len(self.axes) else self.axes[0]
                self.axis = default_axis
                self.saved_axis = default_axis
            
            # Load serial number
            saved_serial = self.settings_manager.get_setting(self.stepper_num, "serial")
            if saved_serial in self.serial_numbers:
                self.serial_number = saved_serial
                self.saved_serial = saved_serial
            elif self.serial_numbers:
                self.serial_number = self.serial_numbers[0]
                self.saved_serial = self.serial_numbers[0]
            
            # Debug log the loaded settings
            logger.debug(f"Loaded settings for {self.id}:")
            logger.debug(f"  Axis: {self.axis}")
            logger.debug(f"  Serial: {self.serial_number}")
            logger.debug(f"  Current Limit: {self.current_limit}")
            logger.debug(f"  Max Speed: {self.max_speed}")
            logger.debug(f"  Divisions: {self.divisions}")
            logger.debug(f"  Min Position: {self.min_position}")
            logger.debug(f"  Max Position: {self.max_position}")
            
            # Update the UI widgets with the loaded values
            self.update_widget_values()
            
            # Set up intervals with non-async functions
            self.set_interval(0.1, self.watch_current_position)
            self.set_interval(0.1, self.watch_target_position)
            self.set_interval(0.1, self.update_scan_state)
            
            # Enable/disable buttons based on initial state
            power_button = self.query_one("#power_stepper", Button)
            power_button.disabled = False  # On button should always be enabled
            
            energize_button = self.query_one("#energize_stepper", Button)
            energize_button.disabled = not self.initialized
            
            zero_button = self.query_one("#zero_stepper", Button)
            zero_button.disabled = not (self.initialized and self.energized)
            
            run_button = self.query_one("#run_stepper", Button)
            run_button.disabled = not self.validate_scan_parameters()
            
            logger.info(f"Successfully loaded settings for {self.id}")
            
        except Exception as e:
            logger.error(f"Error in on_mount: {e}")

    def update_widget_values(self) -> None:
        """Update widget values after they're mounted"""
        try:
            # Update input values - use default "0" if value is None
            self.query_one("#divisions_stepper").value = str(self.divisions or "0")
            self.query_one("#min_position_stepper").value = str(self.min_position or "0")
            self.query_one("#max_position_stepper").value = str(self.max_position or "0")
            self.query_one("#max_speed_stepper").value = str(self.max_speed or "1000")
            
            # Update select values with defaults if needed
            current_select = self.query_one("#current_limit_stepper")
            current_select.value = str(self.current_limit or "2")  # Default to 2 (174mA)
            
            axis_select = self.query_one("#axis_stepper")
            axis_select.value = self.axis or self.axes[0]  # Default to first axis
            
            serial_select = self.query_one("#serial_stepper")
            serial_select.value = self.serial_number or self.serial_numbers[0]  # Default to first serial
            
            # Update title label with current axis
            title_label = self.query_one(f"#{self.id}_title", Label)
            title_label.update(f"{self.axis or self.axes[0]} Control")
            
        except Exception as e:
            logger.error(f"Error updating widget values: {e}")

    def watch_current_position(self) -> None:
        """Watch for changes in current position."""
        try:
            if hasattr(self, 'tic') and self.tic and self.energized:
                # Get current position from motor
                self.current_position = self.tic.get_current_position()
                self.query_one(CurrentPositionDisplay).current_position = self.current_position
                self.moving = self.tic.get_current_position() != self.tic.get_target_position()
                
                # Update progress display when scanning
                if self.scan_state != ScanState.IDLE:
                    progress = self.query_one(ProgressDisplay)
                    logger.debug(f"{self.id}: Updating progress - current_pos={self.current_position}, "
                               f"scan_state={self.scan_state}")
                    progress.update_progress(self.current_position)
                
                if self.moving:
                    logger.debug(f"{self.id} current position: {self.current_position}")
                    logger.debug(f"{self.id} target position: {self.target_position}")
                    
                    # Update position in a simpler way - no queue
                    if self.position_queue:
                        try:
                            # Use put_nowait to avoid blocking
                            self.position_queue.put_nowait({
                                'axis': self.axis,
                                'position': self.current_position
                            })
                        except Exception as e:
                            logger.warning(f"Error updating position: {e}")
        
        except Exception as e:
            logger.error(f"Error watching current position: {e}")

    def watch_target_position(self) -> None:
        """Watch for target position changes and update motor"""
        if hasattr(self, 'tic') and self.tic and self.energized:
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
        
        logger.info(f"{self.id} zeroed - Current position: {self.current_position}, Target position: {self.target_position}")

    def update_initialized(self, event: Button.Pressed) -> None:
        """Update the initialized state of the stepper motor"""
        try:
            logger.debug(f"Updating initialized state for {self.id}")
            if not self.initialized:
                logger.debug(f"Attempting to initialize motor with serial {self.serial_number}")
                # Try to connect to the motor
                self.tic = TicUSB(serial_number=self.serial_number)
                self.initialized = True
                event.button.label = "Off"
                event.button.variant = "error"
                
                # Enable the energize button
                energize_button = self.query_one("#energize_stepper")
                energize_button.disabled = False
                
                logger.info(f"Successfully initialized motor {self.id}")
            else:
                logger.debug("De-initializing motor")
                # Disconnect from motor
                if self.tic:
                    self.tic = None
                self.initialized = False
                event.button.label = "On"
                event.button.variant = "default"
                
                # Disable other buttons
                energize_button = self.query_one("#energize_stepper")
                energize_button.disabled = True
                
                zero_button = self.query_one("#zero_stepper")
                zero_button.disabled = True
                
                run_button = self.query_one("#run_stepper")
                run_button.disabled = True
                
                logger.info(f"De-initialized motor {self.id}")
        except Exception as e:
            logger.error(f"Error updating initialized state: {e}")

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
                logger.debug(f"{self.id} current limit set to: {self.current_limit}")
                self.tic.set_current_limit(int(self.current_limit))
                
            self.tic.energize()
            self.tic.exit_safe_start()
            
        self.update_control_states()

    def update_control_states(self) -> None:
        """Update control states based on current motor state"""
        try:
            # Get all configuration controls
            config_controls = ['axis_stepper', 'serial_stepper', 'current_limit_stepper', 'max_speed_stepper']
            
            # Update enabled/disabled state for each control
            for control_id in config_controls:
                control = self.query_one(f"#{control_id}")
                if self.initialized:
                    control.remove_class("enabled")
                else:
                    control.add_class("enabled")

            # Update current limit display
            current_limit_display = self.query_one("#current_limit_stepper")
            current_limit_display.value = str(self.current_limit)  # Convert to string

            # Update max speed display
            max_speed_display = self.query_one("#max_speed_stepper")
            max_speed_display.value = str(self.max_speed)  # Convert to string

            # Update divisions display
            divisions_display = self.query_one("#divisions_stepper")
            divisions_display.value = str(self.divisions)  # Convert to string

            # Update min position display
            min_position_display = self.query_one("#min_position_stepper")
            min_position_display.value = str(self.min_position)  # Convert to string

            # Update max position display
            max_position_display = self.query_one("#max_position_stepper")
            max_position_display.value = str(self.max_position)  # Convert to string

            # Power button (disabled during scan)
            power_button = self.query_one("#power_stepper")
            power_button.disabled = self.scan_state != ScanState.IDLE
            
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
                control.disabled = not self.initialized or self.scan_state != ScanState.IDLE
                if not control.disabled:
                    control.add_class("enabled")
                else:
                    control.remove_class("enabled")

            # Scan button (enabled when ON and ENERGIZED, or when scanning is in progress)
            scan_button = self.query_one("#run_stepper")
            scan_button.disabled = not ((self.initialized and self.energized) or self.scan_state != ScanState.IDLE)
            scan_button.label = "Stop" if self.scan_state != ScanState.IDLE else "Scan"
            if not scan_button.disabled:
                scan_button.add_class("enabled")
            else:
                scan_button.remove_class("enabled")

        except Exception as e:
            logger.error(f"Error updating control states: {e}")

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
        logger.debug(f"{self.id} target position: {self.target_position}")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle a button press"""
        logger.debug(f"{self.id} button pressed: {event.button.id}")
        
        try:
            if event.button.id == "power_stepper":
                logger.debug("Power button pressed, attempting to initialize motor")
                self.update_initialized(event)
            elif event.button.id == "energize_stepper":
                logger.debug("Energize button pressed")
                self.update_energized(event)
            elif event.button.id == "zero_stepper":
                logger.debug("Zero button pressed")
                self.zero_stepper()
            elif event.button.id == "run_stepper":
                logger.debug("Run button pressed")
                if self.scan_state == ScanState.IDLE:
                    self.start_scan()
                else:
                    self.stop_scan()
        except Exception as e:
            logger.error(f"Error handling button press: {e}")

    @on(Input.Changed)
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle an input change"""
        if event.input.id == "divisions_stepper":
            self.divisions = event.value
            logger.debug(f"Setting divisions for stepper_{self.stepper_num}: {event.value}")
            
        elif event.input.id == "min_position_stepper":
            numbers = re.findall(r"[-+]?(?:\d*\.*\d+)", event.value)
            value = numbers[0] if numbers else ""
            self.min_position = value
            logger.debug(f"Setting min_position for stepper_{self.stepper_num}: {value}")
            
        elif event.input.id == "max_position_stepper":
            numbers = re.findall(r"[-+]?(?:\d*\.*\d+)", event.value)
            value = numbers[0] if numbers else ""
            self.max_position = value
            logger.debug(f"Setting max_position for stepper_{self.stepper_num}: {value}")
        
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
                
                # Update display
                self.max_speed = speed
                logger.debug(f"Setting max_speed for stepper_{self.stepper_num}: {speed}")
                
            except (ValueError, TypeError):
                # Invalid input - reset to previous value
                event.input.value = str(self.max_speed)
        
        # Update Run button state
        run_button = self.query_one("#run_stepper")
        run_button.disabled = not self.validate_scan_parameters()

    @on(Select.Changed)
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select change events."""
        if event.select.id == "axis_stepper":
            self.axis = event.value
            logger.debug(f"{self.id} axis: {self.axis}")
            
            # Update the title to match the selected axis
            title_label = self.query_one(f"#{self.id}_title", Label)
            title_label.update(f"{event.value} Control")
            
        elif event.select.id == "serial_stepper":
            self.serial_number = event.value
            logger.debug(f"{self.id} serial number: {self.serial_number}")
            
        elif event.select.id == "current_limit_stepper":
            self.current_limit = event.value
            # Get the mA value from the options tuple for display
            current_ma = next(opt[0] for opt in self.current_limit_options if opt[1] == event.value)
            logger.debug(f"{self.id} current limit set to: {current_ma}")
            
            # Update the motor if it's connected
            if self.tic:
                self.tic.set_current_limit(int(event.value))
                self.tic.exit_safe_start()

    def compose(self) -> ComposeResult:
        """Create child widgets for the stepper motor"""
        # Add a title for the stepper motor
        yield Label(f"{self.name} Control", id=f"{self.id}_title", classes="stepper-title")
        
        # Configuration controls - only enabled when OFF
        yield Select(
            options=[(axis, axis) for axis in self.axes],
            id="axis_stepper",
            value=self.axes[0],
            allow_blank=True,
            prompt="Select axis"
        )
        yield Select(
            options=[(serial, serial) for serial in self.serial_numbers],
            id="serial_stepper",
            value=self.serial_numbers[0],
            allow_blank=True,
            prompt="Select device"
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
        # Add the progress display
        yield ProgressDisplay(id=f"progress_display_{self.stepper_num}")
        

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
        """Update the scan state and notify scan manager via queue"""
        try:
            if self.scan_state != ScanState.IDLE:
                # Send status update to scan manager
                status = StepperStatus(
                    stepper_num=self.stepper_num,
                    axis=self.axis,
                    current_position=self.current_position,
                    target_position=self.target_position,
                    scan_state=self.scan_state,
                    current_division=self.current_division,
                    total_divisions=len(self.get_division_positions())
                )
                self.scan_manager_queue.put((StepperMessage.STATUS, status))

                if self.scan_state == ScanState.MOVING:
                    if self.current_position == self.target_position:
                        self.scan_state = ScanState.WAITING
                        logger.debug(f"Motor {self.id} reached target, entering wait state")
                        
                        # If this is the forward axis motor (stepper_1), request photo
                        if self.stepper_num == 1:  # Forward axis
                            try:
                                message = {
                                    'message_type': CameraMessage.TAKE_PHOTO,
                                    'position': self.current_position,
                                    'axis': self.axis
                                }
                                self.camera_photo_queue.put(message)
                                logger.info(f"Requested photo at position {self.current_position}")
                            except Exception as e:
                                logger.error(f"Failed to request photo: {e}")

        except Exception as e:
            logger.error(f"Error updating scan state: {e}")

    def continue_scan(self) -> None:
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
            
            # No need to update progress display here since watch_current_position 
            # will handle progress updates during movement
            self.scan_state = ScanState.MOVING

    def start_scan(self) -> None:
        """Start a new scan"""
        if not self.validate_scan_parameters():
            logger.warning(f"{self.id}: Invalid scan parameters")
            return
        
        positions = self.get_division_positions()
        if not positions:
            logger.warning(f"{self.id}: No positions calculated for scan")
            return
        
        # Reset scan state
        self.current_division = 0
        self.target_position = positions[0]
        
        # Initialize progress display with min/max positions
        progress = self.query_one(ProgressDisplay)
        logger.info(f"{self.id}: Starting scan - min_pos={self.min_position}, max_pos={self.max_position}, "
                    f"divisions={len(positions)}")
        progress.set_range(float(self.min_position), float(self.max_position))
        
        # Start state machine
        self.scan_state = ScanState.MOVING
        
        # Update button states for scanning
        self.update_control_states()
        
        logger.info(f"{self.id} starting scan with {len(positions)} positions")

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
            logger.info(f"{self.id} motor halted at position {current_pos}")
        
        # Reset scan state
        self.scan_state = ScanState.IDLE
        self.current_division = 0
        
        # Reset progress display range
        progress = self.query_one(ProgressDisplay)
        logger.debug(f"{self.id}: Resetting progress display")
        progress.set_range(0, 0)  # Reset range to show empty progress
        
        # Update displays
        current_pos_display = self.query_one(CurrentPositionDisplay)
        target_pos_display = self.query_one(TargetPositionDisplay)
        current_pos_display.update_current_position(self.current_position)
        target_pos_display.update_target_position(self.target_position)
        
        # Update button states after scan
        self.update_control_states()
        
        logger.info(f"{self.id} scan stopped")

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
        try:
            # Stop all intervals
            self.set_interval(0.1, self.watch_current_position, pause=True)
            self.set_interval(0.1, self.watch_target_position, pause=True)
            self.set_interval(0.1, self.update_scan_state, pause=True)
            
            # Stop any active timer
            if self._wait_timer:
                self._wait_timer.stop()
                self._wait_timer = None
            
            # Ensure motor is deenergized
            if self.tic:
                try:
                    self.tic.deenergize()
                    self.tic = None
                except:
                    pass

            # Save settings before unmounting
            if self.settings_manager:
                stepper_key = f"stepper_{self.stepper_num}"
                settings = {
                    "axis": self.axis,
                    "serial": self.serial_number,
                    "current_limit": self.current_limit,
                    "max_speed": self.max_speed,
                    "divisions": self.divisions,
                    "min_position": self.min_position,
                    "max_position": self.max_position
                }
                self.settings_manager.settings[stepper_key] = settings
            
        except Exception as e:
            logger.error(f"Error during unmount cleanup: {e}")

    def get_available_ports(self) -> list[str]:
        """Get list of available USB ports for Tic devices"""
        # Return the serial numbers of connected Tic devices
        return self.serial_numbers if self.serial_numbers else []

    def update_status(self) -> None:
        # This method should be implemented to update the status of the stepper motor
        # based on the selected USB port.
        pass

    def load_settings(self):
        """Load saved settings for this stepper motor."""
        if self.settings_manager and hasattr(self.settings_manager, 'settings'):
            stepper_key = f"stepper_{self.stepper_num}"
            if stepper_key in self.settings_manager.settings:
                settings = self.settings_manager.settings[stepper_key]
                
                # Load settings (removed usb_id)
                self.axis = settings.get("axis", "")
                self.serial_number = settings.get("serial", "")
                self.current_limit = settings.get("current_limit", "0")
                # ... rest of settings loading ...

    def move_to_position(self, position: float) -> None:
        """Move to specified position and update state"""
        if not self.energized or not self.initialized:
            return
        
        self.target_position = position
        self.scan_state = ScanState.MOVING
        logger.info(f"{self.id} moving to position {position}")