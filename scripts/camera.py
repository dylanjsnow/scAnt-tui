import os
import subprocess
import time
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid
from textual.widgets import Button, Label, Select, Static
from textual.reactive import reactive
from textual import work

class CameraManager(Static):
    """A widget to manage camera operations."""
    
    status = reactive("Ready")
    
    def __init__(self, id: str = "camera_manager"):
        """Initialize the camera manager."""
        super().__init__(id=id)
        self.cameras = []
        self.selected_camera = None
        
    def compose(self) -> ComposeResult:
        """Compose the camera manager widget."""
        # Main container
        with Grid(id="camera_grid"):
            # Title
            yield Label("Camera Control", id="camera_title", classes="section-title")
            
            # Camera selection dropdown
            self.cameras = self.get_connected_cameras()
            camera_options = [(camera, camera) for camera in self.cameras]
            
            # Camera selection area
            with Horizontal(id="camera_selection_area", classes="control-row"):
                if camera_options:
                    yield Select(
                        options=camera_options,
                        prompt="Select Camera",
                        id="camera_select",
                        classes="camera-select"
                    )
                else:
                    yield Label("No cameras detected", id="no_camera_label", classes="info-label")
            
            # Camera control buttons
            with Horizontal(id="camera_controls", classes="control-row"):
                yield Button("Take Photo", id="take_photo_btn", variant="primary", classes="action-button")
            
            # Status display
            with Horizontal(id="camera_status_area", classes="status-row"):
                yield Label(self.status, id="camera_status", classes="status-label")
    
    def on_mount(self) -> None:
        """Handle the mount event."""
        # Disable the take photo button if no cameras are available
        take_photo_btn = self.query_one("#take_photo_btn", Button)
        take_photo_btn.disabled = len(self.cameras) == 0
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle camera selection change."""
        if event.select.id == "camera_select":
            self.selected_camera = event.value
            self.status = f"Camera selected: {self.selected_camera}"
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "take_photo_btn":
            if self.selected_camera:
                self.take_photo()
            else:
                self.status = "Please select a camera first"
    
    def get_connected_cameras(self) -> list:
        """Get a list of connected cameras using gphoto2."""
        try:
            # Run gphoto2 command to list cameras
            result = subprocess.run(
                ["gphoto2", "--auto-detect"], 
                capture_output=True, 
                text=True, 
                check=True
            )
            print("Connected Cameras: ", result.stdout)
            
            # Parse the output to extract camera models
            lines = result.stdout.strip().split('\n')
            cameras = []
            
            # Skip the header lines
            for line in lines[2:]:  # Skip the first two lines which are headers
                if line.strip():
                    # Extract camera model from the line
                    parts = line.split('usb:')
                    if len(parts) > 0:
                        camera_model = parts[0].strip()
                        cameras.append(camera_model)
            
            return cameras
        except subprocess.CalledProcessError:
            self.status = "Error detecting cameras"
            return []
        except Exception as e:
            self.status = f"Error: {str(e)}"
    
    @work
    async def take_photo(self) -> None:
        """Take a photo with the selected camera."""
        # Create results directory if it doesn't exist
        os.makedirs("./results", exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"./results/{timestamp}.jpg"
        
        self.status = "Taking photo..."
        
        try:
            # Run gphoto2 command to capture image
            self.status = "Waiting for camera..."
            
            result = subprocess.run(
                ["gphoto2", "--camera", self.selected_camera, "--capture-image-and-download", f"--filename={filename}"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.status = f"Photo saved to {filename}"
            else:
                self.status = f"Error capturing photo: {result.stderr}"
        
        except Exception as e:
            self.status = f"Error: {str(e)}"
