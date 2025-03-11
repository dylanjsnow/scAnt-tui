from textual.widgets import Static, Button
from textual.reactive import reactive
from utils import ScanState
from textual.app import ComposeResult
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class ScanManager(Static):
    """Manages coordinated scanning across all stepper motors"""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stepper_motors = []
        self.scanning = False
        logger.debug("ScanManager initialized")
        
    def on_mount(self) -> None:
        """Get references to stepper motors after mount"""
        # Wait briefly to ensure steppers are mounted
        def get_steppers():
            try:
                self.stepper_motors = [
                    self.app.query_one("#stepper_motor_1"),
                    self.app.query_one("#stepper_motor_2"), 
                    self.app.query_one("#stepper_motor_3")
                ]
                logger.debug(f"Found {len(self.stepper_motors)} stepper motors")
            except Exception as e:
                logger.error(f"Error getting stepper motors: {e}")
            
        self.set_timer(0.1, get_steppers)
        logger.debug("ScanManager mounted")
        
    def compose(self) -> ComposeResult:
        """Create child widgets for scan management"""
        yield Button("Start Full Scan", id="start_full_scan", variant="success")
        yield Button("Stop All", id="stop_all_scan", variant="error")
        logger.debug("ScanManager widgets composed")
        
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses"""
        try:
            button_id = event.button.id
            logger.info(f"Scan button pressed: {button_id}")
            
            if event.button.id == "start_full_scan":
                self.start_full_scan()
            elif event.button.id == "stop_all_scan":
                self.stop_all_scans()
                
        except Exception as e:
            logger.error(f"Error handling button press: {e}")
            
    def start_full_scan(self) -> None:
        """Start a coordinated scan across all motors"""
        if not self.stepper_motors:
            logger.warning("No stepper motors available for scanning")
            return
            
        # Check if all motors are ready
        ready_motors = []
        for motor in self.stepper_motors:
            if motor.validate_scan_parameters():
                ready_motors.append(motor)
                logger.debug(f"Motor {motor.id} ready for scanning")
            else:
                logger.warning(f"Motor {motor.id} not ready for scanning")
                
        if not ready_motors:
            logger.warning("No motors ready for scanning")
            return
            
        # Start scan on all ready motors
        self.scanning = True
        for motor in ready_motors:
            motor.start_scan()
            logger.info(f"Started scan on motor {motor.id}")
            
        # Update button states
        try:
            start_button = self.query_one("#start_full_scan")
            start_button.disabled = True
            stop_button = self.query_one("#stop_all_scan") 
            stop_button.disabled = False
            logger.debug("Scan buttons updated")
        except Exception as e:
            logger.error(f"Error updating scan buttons: {e}")
        
        # Set up monitoring of scan completion
        self.set_interval(0.1, self.check_scan_completion)
        logger.debug("Scan completion monitoring started")
        
    def stop_all_scans(self) -> None:
        """Stop scanning on all motors"""
        if not self.stepper_motors:
            logger.warning("No stepper motors available to stop")
            return
            
        self.scanning = False
        for motor in self.stepper_motors:
            if motor.scan_state != ScanState.IDLE:
                motor.stop_scan()
                logger.info(f"Stopped scan on motor {motor.id}")
                
        # Update button states
        try:
            start_button = self.query_one("#start_full_scan")
            start_button.disabled = False
            stop_button = self.query_one("#stop_all_scan")
            stop_button.disabled = True
            logger.debug("Scan buttons updated after stop")
        except Exception as e:
            logger.error(f"Error updating scan buttons after stop: {e}")
        
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
            logger.info("All motors completed scanning")
            
            # Update button states
            try:
                start_button = self.query_one("#start_full_scan")
                start_button.disabled = False
                stop_button = self.query_one("#stop_all_scan")
                stop_button.disabled = True
                logger.debug("Scan buttons updated after completion")
            except Exception as e:
                logger.error(f"Error updating scan buttons after completion: {e}")
                
            return False  # Stop the interval
            
        return True  # Continue checking
