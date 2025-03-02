import os
import subprocess
import time
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid
from textual.widgets import Button, Label, Select, Static, Input
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
        self.current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.subject = "Scan"
        self.owner = "User"
        self.detail = "yaw0_tilt0_forward0"
        self._date_timer = None
        
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
            
            # File naming options
            with Grid(id="file_naming_grid", classes="file-naming-section"):
                # Date (auto-generated, read-only)
                yield Label("Date:", classes="field-label")
                yield Input(
                    value=self.current_date,
                    id="date_input",
                    disabled=True,
                    classes="field-input readonly"
                )
                
                # Subject (user input)
                yield Label("Subject:", classes="field-label")
                yield Input(
                    value=self.subject,
                    id="subject_input",
                    placeholder="Enter subject",
                    classes="field-input"
                )
                
                # Owner (user input)
                yield Label("Owner:", classes="field-label")
                yield Input(
                    value=self.owner,
                    id="owner_input",
                    placeholder="Enter owner",
                    classes="field-input"
                )
                
                # Detail (auto-generated from stepper positions, read-only)
                yield Label("Detail:", classes="field-label")
                yield Input(
                    value=self.detail,
                    id="detail_input",
                    disabled=True,
                    classes="field-input readonly"
                )
            
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
        
        # Update the date field with current timestamp
        self.update_date_field()
        
        # Update the detail field with current stepper positions
        self.update_detail_field()
        
        # Set up a timer to update the date every second
        self._date_timer = self.set_interval(1.0, self.update_date_field)
    
    def update_date_field(self) -> None:
        """Update the date field with current timestamp."""
        self.current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_input = self.query_one("#date_input", Input)
        date_input.value = self.current_date
    
    def update_detail_field(self) -> None:
        """Update the detail field with current stepper positions."""
        # This would normally get the actual stepper positions
        # For now, we'll use placeholder values
        try:
            # Try to import the necessary modules to get stepper positions
            from scripts.current_position import CurrentPositionDisplay
            
            # Find all stepper motors in the app
            app = self.app
            yaw_position = 0
            tilt_position = 0
            forward_position = 0
            
            # Try to get the current positions from the app
            for widget in app.query(CurrentPositionDisplay):
                if "yaw" in widget.id.lower():
                    yaw_position = widget.value
                elif "tilt" in widget.id.lower():
                    tilt_position = widget.value
                elif "forward" in widget.id.lower():
                    forward_position = widget.value
            
            self.detail = f"yaw{yaw_position}_tilt{tilt_position}_forward{forward_position}"
        except (ImportError, AttributeError):
            # If we can't get the actual positions, use defaults
            self.detail = "yaw0_tilt0_forward0"
        
        detail_input = self.query_one("#detail_input", Input)
        detail_input.value = self.detail
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input field changes."""
        if event.input.id == "subject_input":
            self.subject = event.value
        elif event.input.id == "owner_input":
            self.owner = event.value
    
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
            return []
    
    @work
    async def take_photo(self) -> None:
        """Take a photo with the selected camera."""
        # Create results directory if it doesn't exist
        os.makedirs("./results", exist_ok=True)
        
        # Update date and detail fields before taking the photo
        self.update_date_field()
        self.update_detail_field()
        
        # Generate filename with all components
        filename = f"./results/{self.current_date}_{self.subject}_{self.owner}_{self.detail}.jpg"
        
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
            
    def on_unmount(self) -> None:
        """Clean up when widget is removed."""
        if self._date_timer:
            self._date_timer.stop()
