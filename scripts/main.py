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
            logger.info("Initialized position and camera photo queues")
            logger.info("Settings manager initialized successfully")
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
                    camera_photo_queue=self.camera_photo_queue,  # Pass the new queue
                    settings_manager=self.settings_manager
                )
                
                # Stepper motors in a vertical container
                with Vertical(id="stepper_container"):
                    logger.info("Creating stepper motor instances")
                    for i in range(3):
                        yield StepperMotor(
                            settings_manager=self.settings_manager,
                            position_queue=self.position_queue,
                            camera_photo_queue=self.camera_photo_queue,  # Pass the new queue
                            stepper_num=i+1
                        )
            
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
            
            # Then close the queue
            if hasattr(self, 'position_queue'):
                # Drain the queue first
                while not self.position_queue.empty():
                    try:
                        self.position_queue.get_nowait()
                    except queue.Empty:
                        break
                self.position_queue.close()
                self.position_queue.join_thread()
            
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
