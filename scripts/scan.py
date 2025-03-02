from textual.widgets import Static, Button
from textual.reactive import reactive
from utils import ScanState
from textual.app import ComposeResult

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
