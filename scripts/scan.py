from textual.widgets import Static, Button
from textual.reactive import reactive
from utils import ScanState
from textual.app import ComposeResult
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class ScanManager(Static):
    """Manages coordinated scanning across all stepper motors"""
    
    def __init__(
        self,
        stepper_motors=None,
        camera=None,
        *args,
        **kwargs
    ):
        """Initialize the scan manager with stepper motors and camera"""
        # Initialize parent class first, without our custom kwargs
        super().__init__(*args)  # Only pass args, not kwargs
        
        # Store stepper motors and camera
        self.stepper_motors = stepper_motors if stepper_motors else []
        self.camera = camera
        self.scanning = False
        
        if self.stepper_motors:
            logger.info(f"Successfully found and stored {len(self.stepper_motors)} stepper motors")
        else:
            logger.warning("No stepper motors provided to ScanManager")
            
        if self.camera:
            logger.info("Successfully stored camera reference")
        else:
            logger.warning("No camera provided to ScanManager")
        
    def on_mount(self) -> None:
        """Get references to stepper motors after mount"""
        # Wait briefly to ensure steppers are mounted
        def get_steppers():
            try:
                self.stepper_motors = [
                    self.app.query_one("#stepper_1"),
                    self.app.query_one("#stepper_2"), 
                    self.app.query_one("#stepper_3")
                ]
                logger.info(f"Successfully found and stored {len(self.stepper_motors)} stepper motors: {[motor.id for motor in self.stepper_motors]}")
            except Exception as e:
                logger.error(f"Error getting stepper motors: {e}")
                # Try again after a short delay
                self.set_timer(0.5, get_steppers)
            
        self.set_timer(0.1, get_steppers)
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
            
    def start_full_scan(self) -> None:
        """Start a coordinated scan across all motors"""
        if not self.stepper_motors:
            logger.warning("Cannot start scan - no stepper motors available")
            return
            
        logger.info("Starting full scan across all motors")
        self.scanning = True
        # Start scan on each motor
        for motor in self.stepper_motors:
            if motor:
                motor.start_scan()
            
        # Update button states
        try:
            start_button = self.query_one("#start_full_scan")
            start_button.disabled = True
            logger.debug("Scan buttons updated")
        except Exception as e:
            logger.error(f"Error updating scan buttons: {e}")
        
        # Set up monitoring of scan completion
        self.set_interval(0.1, self.check_scan_completion)
        logger.debug("Scan completion monitoring started")
        
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
                logger.debug("Scan buttons updated after completion")
            except Exception as e:
                logger.error(f"Error updating scan buttons after completion: {e}")
                
            return False  # Stop the interval
            
        return True  # Continue checking

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
