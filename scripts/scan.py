from textual.widgets import Static, Button
from textual.reactive import reactive
from utils import ScanState, StepperStatus, StepperMessage
from textual.app import ComposeResult
import logging
from queue import Queue
from typing import Dict

# Create logger for this module
logger = logging.getLogger(__name__)

class ScanManager(Static):
    """Manages coordinated scanning across all stepper motors"""
    
    def __init__(
        self,
        stepper_motors=None,
        camera=None,
        scan_manager_queue=None,
        *args,
        **kwargs
    ):
        """Initialize the scan manager with stepper motors and camera"""
        # Initialize parent class first, without our custom kwargs
        super().__init__(*args)  # Only pass args, not kwargs
        
        # Store stepper motors and camera
        self.stepper_motors = stepper_motors
        self.camera = camera
        self.scanning = False
        self.scan_manager_queue = scan_manager_queue
        self.stepper_statuses: Dict[int, StepperStatus] = {}
        
        if self.stepper_motors:
            logger.info(f"Successfully found and stored {len(self.stepper_motors)} stepper motors")
        else:
            logger.warning("No stepper motors provided to ScanManager")
            
        if self.camera:
            logger.info("Successfully stored camera reference")
        else:
            logger.warning("No camera provided to ScanManager")
        
        # Set up monitoring of scan queue
        self.set_interval(0.1, self.process_queue)
        
    def on_mount(self) -> None:
        """Get references to stepper motors after mount"""
        logger.debug("ScanManager mounted")
        
    def compose(self) -> ComposeResult:
        """Create child widgets for scan management"""
        yield Button("Start Full Scan", id="start_full_scan", variant="success")
        yield Button("EMERGENCY STOP", id="emergency_stop", variant="error", classes="emergency-stop")
        logger.debug("ScanManager widgets composed")
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        try:
            button_id = event.button.id
            logger.info(f"Scan button pressed: {button_id}")
            
            if event.button.id == "start_full_scan":
                self.start_full_scan()
            elif event.button.id == "emergency_stop":
                self.emergency_stop()
                
        except Exception as e:
            logger.error(f"Error handling button press: {e}")
            
    def process_queue(self) -> None:
        """Process messages from the scan manager queue"""
        try:
            while not self.scan_manager_queue.empty():
                message_type, data = self.scan_manager_queue.get_nowait()
                
                if message_type == StepperMessage.STATUS:
                    self.stepper_statuses[data.stepper_num] = data
                    self.handle_scan_sequence()
                    
        except Exception as e:
            logger.error(f"Error processing queue: {e}")

    def handle_scan_sequence(self) -> None:
        """Handle the scanning sequence based on current stepper statuses"""
        if not self.scanning:
            return

        try:
            # Get status for each motor
            fwd_status = self.stepper_statuses.get(1)  # Forward (stepper 1)
            yaw_status = self.stepper_statuses.get(2)  # Yaw (stepper 2)
            tilt_status = self.stepper_statuses.get(3)  # Tilt (stepper 3)

            if not all([fwd_status, yaw_status, tilt_status]):
                return

            # All motors in WAITING state - decide next move
            if all(status.scan_state == ScanState.WAITING for status in [fwd_status, yaw_status, tilt_status]):
                logger.debug("All motors in WAITING state, determining next move")
                
                # Forward hasn't completed its positions
                if fwd_status.current_division < fwd_status.total_divisions - 1:
                    logger.info(f"Moving forward motor to next division {fwd_status.current_division + 1}")
                    self.move_stepper(1)
                
                # Forward complete, move yaw
                elif yaw_status.current_division < yaw_status.total_divisions - 1:
                    logger.info(f"Moving yaw motor to next division {yaw_status.current_division + 1}")
                    # Reset forward position
                    self.move_stepper(1, division=0)
                    self.move_stepper(2)
                
                # Yaw complete, move tilt
                elif tilt_status.current_division < tilt_status.total_divisions - 1:
                    logger.info(f"Moving tilt motor to next division {tilt_status.current_division + 1}")
                    # Reset yaw and forward positions
                    self.move_stepper(1, division=0)
                    self.move_stepper(2, division=0)
                    self.move_stepper(3)
                
                # All complete
                else:
                    logger.info("Scan sequence complete")
                    self.scanning = False
                    # Update button states
                    try:
                        start_button = self.query_one("#start_full_scan")
                        start_button.disabled = False
                    except Exception as e:
                        logger.error(f"Error updating button state: {e}")

        except Exception as e:
            logger.error(f"Error handling scan sequence: {e}")

    def move_stepper(self, stepper_num: int, division: int = None) -> None:
        """Move specified stepper to next division or specific division"""
        try:
            stepper = next((m for m in self.stepper_motors if m.stepper_num == stepper_num), None)
            if stepper:
                if division is None:
                    # Move to next division
                    stepper.continue_scan()
                else:
                    # Move to specific division
                    positions = stepper.get_division_positions()
                    if 0 <= division < len(positions):
                        stepper.current_division = division
                        stepper.move_to_position(positions[division])
                logger.info(f"Moving stepper {stepper_num} to division {division if division is not None else 'next'}")
        except Exception as e:
            logger.error(f"Error moving stepper: {e}")

    def start_full_scan(self) -> None:
        """Start a coordinated scan across all motors"""
        if not self.stepper_motors:
            logger.warning("Cannot start scan - no stepper motors available")
            return
            
        logger.info("Starting full scan across all motors")
        self.scanning = True
        self.stepper_statuses.clear()
        
        # Move all motors to their initial positions
        for motor in self.stepper_motors:
            if motor:
                motor.start_scan()
        
        # Update button states
        try:
            start_button = self.query_one("#start_full_scan")
            start_button.disabled = True
        except Exception as e:
            logger.error(f"Error updating scan buttons: {e}")
        
    def emergency_stop(self) -> None:
        """Emergency stop all motors"""
        logger.info("Emergency stop triggered")
        self.scanning = False
        # Stop all motors
        for motor in self.stepper_motors:
            if motor:
                motor.stop_scan()
            
        # Update button states
        try:
            start_button = self.query_one("#start_full_scan")
            start_button.disabled = False
            logger.debug("Scan buttons updated after emergency stop")
        except Exception as e:
            logger.error(f"Error updating scan buttons after emergency stop: {e}")
