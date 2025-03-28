import logging
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Button, TabbedContent, TabPane
from stepper_motor import StepperMotor
from camera import CameraManager
from utils import ScanState
from settings import SettingsManager
from scan import ScanManager
from multiprocessing import Queue
import queue

# Configure logging with more detailed format
logging.basicConfig(
    filename='logs.txt',
    encoding='utf-8',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d]',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# Create logger for this module
logger = logging.getLogger(__name__)

class ScannerApp(App):
    """A Textual app for controlling stepper motors and camera."""
    
    CSS_PATH = "main.tcss"
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("d", "toggle_dark", "Toggle Dark Mode"),
    ]
    
    def __init__(self):
        super().__init__()
        self.settings_manager = None
        logger.info("Initializing ScannerApp")
        try:
            self.settings_manager = SettingsManager("settings.json")
            self.position_queue = Queue()
            self.camera_photo_queue = Queue()  # New queue for photo requests
            self.scan_manager_queue = Queue()  # New queue for scan manager communication
            logger.info("Initialized position and camera photo queues")
            logger.info("Settings manager initialized successfully")
            
            # Initialize stepper motors with their respective numbers
            self.stepper_1 = None  # Forward axis
            self.stepper_2 = None  # Tilt axis
            self.stepper_3 = None  # Yaw axis
            
            # Initialize camera
            self.camera = None
            
            # Initialize scan manager (will be set after steppers are created)
            self.scan_manager = None
        except Exception as e:
            logger.error(f"Failed to initialize settings manager: {e}")
            raise
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        logger.debug("Starting app composition")
        try:
            yield Header()
            
            # Main app container as a vertical layout
            with Container(id="app_container"):
                # Camera manager below the control buttons
                logger.info("Creating camera manager")
                yield CameraManager(
                    position_queue=self.position_queue,
                    camera_photo_queue=self.camera_photo_queue,
                    settings_manager=self.settings_manager
                )
                
                # Stepper motors in a vertical container
                with Vertical(id="stepper_container"):
                    logger.info("Creating stepper motor instances")
                    # Create and store stepper instances
                    self.stepper_1 = StepperMotor(
                        self.settings_manager,
                        self.position_queue,
                        self.camera_photo_queue,
                        self.scan_manager_queue,
                        stepper_num=1,
                        id="stepper_1"
                    )
                    self.stepper_2 = StepperMotor(
                        self.settings_manager,
                        self.position_queue,
                        self.camera_photo_queue,
                        self.scan_manager_queue,
                        stepper_num=2,
                        id="stepper_2"
                    )
                    self.stepper_3 = StepperMotor(
                        self.settings_manager,
                        self.position_queue,
                        self.camera_photo_queue,
                        self.scan_manager_queue,
                        stepper_num=3,
                        id="stepper_3"
                    )
                    
                    # Yield the stepper motors to render them
                    yield self.stepper_1
                    yield self.stepper_2
                    yield self.stepper_3

                # Create camera instance
                self.camera = CameraManager(
                    position_queue=self.position_queue,
                    camera_photo_queue=self.camera_photo_queue,
                    settings_manager=self.settings_manager
                )

                # Create scan manager with stepper motor instances
                self.scan_manager = ScanManager(
                    stepper_motors=[self.stepper_1, self.stepper_2, self.stepper_3],
                    camera=self.camera,
                    scan_manager_queue=self.scan_manager_queue
                )
                
                # Yield the scan manager
                yield self.scan_manager
            
            # yield Footer()
            logger.debug("App composition completed successfully")
            
        except Exception as e:
            logger.error(f"Error during app composition: {e}")
            raise

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses in the main app"""
        try:
            button_id = event.button.id
            logger.info(f"Main app button pressed: {button_id}")
            
            if button_id == "home_all_btn":
                logger.debug("Homing all motors")
                # Press the home button on all motors
                for motor in self.query(StepperMotor):
                    home_button = motor.query_one("#home_stepper")
                    home_button.press()
            
            elif button_id == "stop_all_btn":
                logger.debug("Stopping all motors")
                # Stop scanning on all motors
                for motor in self.query(StepperMotor):
                    scan_button = motor.query_one("#run_stepper")
                    if scan_button.label == "Stop":  # Only stop if currently scanning
                        logger.debug(f"Stopping motor {motor.id}")
                        scan_button.press()
                        
        except Exception as e:
            logger.error(f"Error handling button press: {e}")

    def on_mount(self) -> None:
        """Handle app mount event."""
        logger.info("App mounted")

    async def on_unmount(self) -> None:
        """Clean up when app unmounts."""
        logger.info("App unmounting, cleaning up...")
        try:
            # Save settings first
            if self.settings_manager:
                self.settings_manager.save_all()
            
            # Then close the queues
            if hasattr(self, 'position_queue'):
                # Drain the queue first
                while not self.position_queue.empty():
                    try:
                        self.position_queue.get_nowait()
                    except queue.Empty:
                        break
                self.position_queue.close()
                self.position_queue.join_thread()
                
            # Clean up scan manager queue
            if hasattr(self, 'scan_manager_queue'):
                while not self.scan_manager_queue.empty():
                    try:
                        self.scan_manager_queue.get_nowait()
                    except queue.Empty:
                        break
                self.scan_manager_queue.close()
                self.scan_manager_queue.join_thread()
            
        except Exception as e:
            logger.error(f"Error during app cleanup: {e}")

if __name__ == "__main__":
    try:
        logger.info("Starting ScannerApp")
        app = ScannerApp()
        app.run()
    except Exception as e:
        logger.critical(f"Fatal error in main app: {e}", exc_info=True)
        raise
