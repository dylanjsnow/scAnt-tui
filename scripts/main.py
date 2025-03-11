import logging
from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical, Container
from textual.widgets import Header, Footer, Button, TabbedContent, TabPane
from stepper_motor import StepperMotor
from camera import CameraManager
from utils import ScanState
from settings import SettingsManager

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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        logger.info("Initializing ScannerApp")
        try:
            self.settings_manager = SettingsManager("settings.json")
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
                # Control buttons for all motors at the very top
                with Horizontal(id="control_buttons"):
                    yield Button("Home All", id="home_all_btn", variant="primary")
                    yield Button("Stop All", id="stop_all_btn", variant="error")
                
                # Stepper motors in a vertical container to show in a column
                with Vertical(id="stepper_container"):
                    logger.info("Creating stepper motor instances")
                    # Create stepper motors with shared settings manager
                    for i in range(1, 4):
                        logger.debug(f"Creating stepper motor {i}")
                        yield StepperMotor(stepper_id=str(i), settings_manager=self.settings_manager)
                
                # Camera manager below the control buttons
                logger.info("Creating camera manager")
                yield CameraManager(settings_manager=self.settings_manager)
            
            yield Footer()
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
        """Handle app mount event"""
        logger.info("App mounted")
        
    def on_unmount(self) -> None:
        """Handle app unmount event"""
        logger.info("App unmounting")
        try:
            # Save all settings before shutdown
            self.settings_manager.save_all()
            logger.info("Settings saved on shutdown")
        except Exception as e:
            logger.error(f"Error saving settings on shutdown: {e}")

if __name__ == "__main__":
    try:
        logger.info("Starting ScannerApp")
        app = ScannerApp()
        app.run()
    except Exception as e:
        logger.critical(f"Fatal error in main app: {e}", exc_info=True)
        raise
