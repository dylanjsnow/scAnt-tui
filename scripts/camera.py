import os
import subprocess
import asyncio
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid, ScrollableContainer, Container
from textual.widgets import Button, Label, Select, Static, Input, TextArea
from textual.reactive import reactive
from textual import work
from PIL import Image,  ExifTags
import json
from pathlib import Path
import logging
from utils import CameraState, CameraMessage
from multiprocessing import Queue
import shutil
import gphoto2 as gp
from current_position import CurrentPositionDisplay

# Create logger for this module
logger = logging.getLogger(__name__)

class CameraManager(Static):
    """A widget to manage camera operations."""
    
    status = reactive("Ready")
    
    def __init__(self, camera_queue: Queue, settings_manager=None, id: str = "camera_manager"):
        """Initialize the camera manager."""
        # Keep the super() call to properly initialize the parent widget
        super().__init__(id=id)
        
        self.cameras = []
        self.selected_camera = None
        self.current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.subject = "Scan"
        self.owner = "User"
        
        # Position tracking
        self.yaw_position = "0"
        self.tilt_position = "0" 
        self.forward_position = "0"
        
        self._date_timer = None
        
        # Store reference to settings manager
        self.settings_manager = settings_manager
        
        # Default values for metadata fields
        self.project_name = ""
        self.subject_id = ""
        self.scale = ""
        self.copyright = ""
        self.notes = ""
        self.software = "MacroScans v1.0"

        # Load settings if available
        self.load_settings()
        
        self.camera_queue = camera_queue
        self.state = CameraState.IDLE
        
        logger.info("Initializing CameraManager")
    
    def load_settings(self) -> None:
        """Load camera settings from settings manager."""
        if self.settings_manager and hasattr(self.settings_manager, 'settings'):
            if 'camera' in self.settings_manager.settings:
                camera_settings = self.settings_manager.settings['camera']
                
                # Load user metadata
                self.subject = camera_settings.get("subject", self.subject)
                self.owner = camera_settings.get("owner", self.owner)
                self.yaw_position = camera_settings.get("yaw_position", self.yaw_position)
                self.tilt_position = camera_settings.get("tilt_position", self.tilt_position)
                self.forward_position = camera_settings.get("forward_position", self.forward_position)
                self.project_name = camera_settings.get("project_name", self.project_name)
                self.subject_id = camera_settings.get("subject_id", self.subject_id)
                self.scale = camera_settings.get("scale", self.scale)
                self.copyright = camera_settings.get("copyright", self.copyright)
                self.notes = camera_settings.get("notes", self.notes)
                self.software = camera_settings.get("software", self.software)
                self.selected_camera = camera_settings.get("selected_camera", self.selected_camera)
                
            logger.debug("Loading camera settings")
    
    def save_settings(self) -> None:
        """Save camera settings to the settings manager."""
        if self.settings_manager and hasattr(self.settings_manager, 'settings'):
            try:
                # Create settings dictionary with current instance values
                camera_settings = {
                    "subject": self.subject,
                    "owner": self.owner,
                    "yaw_position": self.yaw_position,
                    "tilt_position": self.tilt_position,
                    "forward_position": self.forward_position,
                    "project_name": self.project_name,
                    "subject_id": self.subject_id,
                    "scale": self.scale,
                    "copyright": self.copyright,
                    "notes": self.notes,
                    "software": self.software,
                    "selected_camera": self.selected_camera
                }
                
                # Update settings and save
                self.settings_manager.settings['camera'] = camera_settings
                self.settings_manager.save_all()
                logger.debug("Camera settings saved successfully")
                
            except Exception as e:
                logger.error(f"Error saving camera settings: {e}")
    
    def compose(self) -> ComposeResult:
        """Create child widgets for the camera manager."""
        # Camera selection and control
        with Container(id="camera_grid"):
            yield Label("Camera Control", id="camera_title", classes="section-title")
            
            # Camera controls in horizontal layout
            with Horizontal(id="camera_controls"):
                # Camera selection dropdown
                self.cameras = self.get_connected_cameras()
                yield Select(
                    options=[(cam, cam) for cam in self.cameras],
                    id="camera_select",
                    prompt="Select camera"
                )
                yield Button("Take Photo", id="take_photo_btn", variant="primary")
                yield Button("Update EXIF Details from Camera", id="update_exif_btn", variant="default")
            
            # File naming grid
            with Container(id="file_naming_grid"):
                # Date (auto-generated, read-only)
                yield Label("Date:", classes="field-label")
                yield Input(
                    value=self.current_date,
                    id="date_input",
                    disabled=True
                )
                
                yield Label("Subject:", classes="field-label")
                yield Input(id="subject_input", value=self.subject)
                
                yield Label("Artist:", classes="field-label")
                yield Input(id="owner_input", value=self.owner)
                
                # Detail (auto-generated from stepper positions)
                yield Label("Detail:", classes="field-label")
                yield Input(
                    value=f"yaw{self.yaw_position}_tilt{self.tilt_position}_forward{self.forward_position}",
                    id="detail_input",
                    disabled=True
                )
                
                yield Label("Project:", classes="field-label")
                yield Input(id="project_input", value=self.project_name)
                
                yield Label("Subject ID:", classes="field-label")
                yield Input(id="subject_id_input", value=self.subject_id)
                
                yield Label("Scale:", classes="field-label")
                yield Input(id="scale_input", value=self.scale)
                
                yield Label("Software:", classes="field-label")
                yield Input(id="software_input", value=self.software)
                
                yield Label("Copyright:", classes="field-label")
                yield Input(id="copyright_input", value=self.copyright)
                
                yield Label("Notes:", classes="field-label")
                yield Input(id="notes_input", value=self.notes)

    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        # Load settings first
        self.load_settings()
        
        try:
            # Select the previously used camera if available
            if self.selected_camera:
                camera_select = self.query_one("#camera_select")
                if camera_select:
                    # Check if the saved camera is in the current options
                    if self.selected_camera in [cam for cam in self.cameras]:
                        camera_select.value = self.selected_camera
                        logger.debug(f"Restored previous camera selection: {self.selected_camera}")
                    else:
                        logger.debug(f"Previously selected camera {self.selected_camera} not found in available cameras")
            
            # Enable the take photo button even if no cameras are available
            take_photo_btn = self.query_one("#take_photo_btn", Button)
            take_photo_btn.disabled = False
            
            # Update the date field with current timestamp
            self.update_date_field()
            
            # Update the detail field with current stepper positions
            self.update_detail_field()
            
            # Set up a timer to update the date every second
            self._date_timer = self.set_interval(1.0, self.update_date_field)
            
            # Start monitoring the queue for photo requests
            self.set_interval(0.1, self.check_queue)
            
            # No need to hide the EXIF container as it's now always visible
            # with individual fields instead of a toggle-able container
        
        except Exception as e:
            logger.error(f"Error in on_mount: {e}")
    
    def update_widget_values(self) -> None:
        """Update widget values after they're mounted"""
        try:
            # Update input values
            self.query_one("#subject_input").value = self.subject
            self.query_one("#owner_input").value = self.owner
            self.query_one("#project_input").value = self.project_name
            self.query_one("#subject_id_input").value = self.subject_id
            self.query_one("#scale_input").value = self.scale
            self.query_one("#software_input").value = self.software
            self.query_one("#copyright_input").value = self.copyright
            self.query_one("#notes_input").value = self.notes
        except Exception as e:
            logger.error(f"Error updating fields from UI: {e}")
    
    
    
    def update_date_field(self) -> None:
        """Update the date field with current timestamp in EXIF format (YYYY:MM:DD HH:MM:SS)."""
        try:
            # Format date according to EXIF standard
            self.current_date = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
            date_input = self.query_one("#date_input")
            if date_input:
                date_input.value = self.current_date
                
                
        except Exception as e:
            logger.error(f"Error updating date field: {e}")
    
    def update_detail_field(self) -> None:
        """Update the detail field with current stepper positions."""
        # This would normally get the actual stepper positions
        # For now, we'll use placeholder values
        try:
            # Try to import the necessary modules to get stepper positions

            
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
            
            self.yaw_position = str(yaw_position)
            self.tilt_position = str(tilt_position)
            self.forward_position = str(forward_position)
        except (ImportError, AttributeError):
            # If we can't get the actual positions, use defaults
            self.yaw_position = "0"
            self.tilt_position = "0"
            self.forward_position = "0"
        
        detail_input = self.query_one("#detail_input", Input)
        detail_input.value = f"yaw{self.yaw_position}_tilt{self.tilt_position}_forward{self.forward_position}"
    
    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle input change events."""
        try:
            # Update instance variables when inputs change
            if event.input.id == "subject_input":
                self.subject = event.value
            elif event.input.id == "owner_input":
                self.owner = event.value
            elif event.input.id == "project_input":
                self.project_name = event.value
            elif event.input.id == "subject_id_input":
                self.subject_id = event.value
            elif event.input.id == "scale_input":
                self.scale = event.value
            elif event.input.id == "software_input":
                self.software = event.value
            elif event.input.id == "copyright_input":
                self.copyright = event.value
            elif event.input.id == "notes_input":
                self.notes = event.value
            
            # Save settings after a short delay
            # self.app.call_later(lambda _: self.save_settings(), 1)
            
        except Exception as e:
            logger.error(f"Error handling input change: {e}")
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select change events."""
        if event.select.id == "camera_select":
            self.selected_camera = event.value
            logger.debug(f"Selected camera: {self.selected_camera}")
            
            # Don't trigger a save here - let the user explicitly save with Update EXIF
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        if event.button.id == "take_photo_btn":
            logger.debug("Take Photo Button Pressed")
            self.take_photo({'position': 0, 'axis': 'test'})
        elif event.button.id == "update_exif_btn":
            logger.debug("Update EXIF Button Pressed")
            self.update_exif_from_camera()
    
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
            logger.debug("Connected Cameras: ", result.stdout)
            
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
    

    
    def update_input_field(self, field_id, value):
        """Safely update an input field if it exists."""
        try:
            input_field = self.query_one(f"#{field_id}", Input)
            input_field.value = str(value)
        except Exception as e:
            logger.error(f"Could not update field {field_id}: {e}")
    
    def create_thumbnail(self, img):
        """Create a thumbnail image for EXIF data."""
        # Create a thumbnail image (160x120)
        thumbnail = img.copy()
        thumbnail.thumbnail((160, 120), Image.LANCZOS)
        
        # Save thumbnail to a bytes buffer
        import io
        thumb_buffer = io.BytesIO()
        thumbnail.save(thumb_buffer, format='JPEG')
        return thumb_buffer.getvalue()
    
    def create_empty_image(self, filename: str) -> bool:
        """Create an empty image with EXIF data."""
        try:
            # Create a small black image
            img = Image.new('RGB', (1280, 720), color='black')
            
            # Create a thumbnail
            thumbnail_data = self.create_thumbnail(img)
            
            # Get EXIF dictionary
            exif_dict = self.get_exif_dict()
            
            # Create EXIF data
            exif = Image.Exif()
            for tag, value in exif_dict.items():
                exif[tag] = value
            
            # Save the image with EXIF data
            img.save(filename, exif=exif)
            
            logger.info(f"Created empty image: {filename}")
            return True
        except Exception as e:
            logger.error(f"Error creating empty image: {e}")
            return False
    
    @work
    async def take_empty_photo(self) -> None:
        """Take a photo without a camera by creating an empty image."""
        # Create results directory if it doesn't exist
        os.makedirs("./results", exist_ok=True)
        
        # Update date and detail fields before taking the photo
        self.update_date_field()
        self.update_detail_field()
        
        # Generate filename with all components
        filename = f"./results/{self.current_date}_{self.subject}_{self.owner}_{f'yaw{self.yaw_position}_tilt{self.tilt_position}_forward{self.forward_position}'}.jpg"
        
        self.status = "Creating empty image..."
        
        try:
            # Create an empty image with metadata
            if self.create_empty_image(filename):
                self.status = f"Empty image saved to {filename}"
            else:
                self.status = "Error creating empty image"
        except Exception as e:
            self.status = f"Error: {str(e)}"
    
    def extract_camera_info(self, camera_model):
        """Extract camera manufacturer and model from camera model string."""
        # Most camera model strings are in the format "Manufacturer Model"
        parts = camera_model.split(' ', 1)
        if len(parts) > 1:
            return parts[0], parts[1]
        else:
            return camera_model, "Unknown"
    
    def check_queue(self) -> None:
        """Check for and handle camera queue messages"""
        try:
            if not self.camera_queue.empty():
                message_type, data = self.camera_queue.get_nowait()
                
                if message_type == CameraMessage.TAKE_PHOTO:
                    if self.state == CameraState.IDLE:
                        self.state = CameraState.CAPTURING
                        # Schedule the async take_photo
                        asyncio.create_task(self.take_photo(data))
                        logger.info(f"Scheduled photo capture at position {data.get('position')}")
                    else:
                        logger.warning(f"Received photo request while camera busy (state: {self.state})")
                        # Put the message back in the queue to try again later
                        self.camera_queue.put((message_type, data))
                        
        except Exception as e:
            logger.error(f"Error checking camera queue: {e}")

    async def _capture_image(self) -> str:
        """Capture an image using gphoto2 and return the path to the captured file."""
        try:
            # Initialize camera
            camera = gp.Camera()
            camera.init()
            
            logger.debug("Capturing image with gphoto2...")
            
            # Capture the image
            file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
            logger.debug(f'Camera file path: {file_path.folder}/{file_path.name}')
            
            # Define target path in results directory
            os.makedirs("./results", exist_ok=True)
            target = os.path.join("./results", f"temp_{file_path.name}")
            
            # Copy image from camera to computer
            logger.debug(f'Copying image to: {target}')
            camera_file = camera.file_get(
                file_path.folder, 
                file_path.name, 
                gp.GP_FILE_TYPE_NORMAL
            )
            camera_file.save(target)
            
            # Clean up
            camera.exit()
            
            return target
            
        except Exception as e:
            logger.error(f"Error capturing image: {e}")
            return None

    @work
    async def take_photo(self, metadata=None):
        """Take a photo with the camera and save it with metadata."""
        try:
            logger.info(f"Taking photo at position {metadata.get('position', 'unknown')} on axis {metadata.get('axis', 'unknown')} axis")
            
            self.state = CameraState.CAPTURING
            
            # Take the photo using gphoto2
            capture_path = await self._capture_image()
            
            if not capture_path:
                logger.error("Failed to capture image")
                self.state = CameraState.IDLE
                return False

            # Create results directory if it doesn't exist
            os.makedirs("./results", exist_ok=True)
            
            # Generate final filename with timestamp and metadata
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            position = metadata.get('position', '0') if metadata else '0'
            axis = metadata.get('axis', 'test') if metadata else 'test'
            final_filename = f"{timestamp}_{self.subject}_{position}_{axis}.jpg"
            final_path = os.path.join("./results", final_filename)
            
            try:
                # First copy the captured image to final location
                shutil.copy2(capture_path, final_path)
                logger.info(f"Photo saved to: {final_path}")

                # Add EXIF data to the saved image
                with Image.open(final_path) as img:
                    if not self.save_image_with_exif(img, final_path):
                        logger.error("Failed to apply EXIF data to image")
                    
            except Exception as e:
                logger.error(f"Error saving photo: {e}")
                self.state = CameraState.IDLE
                return False

            self.state = CameraState.IDLE
            return True

        except Exception as e:
            logger.error(f"Error taking photo: {str(e)}")
            self.state = CameraState.IDLE
            return False

    def on_unmount(self) -> None:
        """Handle unmount event."""
        # Stop the date timer
        if self._date_timer:
            self._date_timer.stop()
        
        # Save settings before unmounting
        self.save_settings()

    def save_image_with_exif(self, img, filename):
        """Save an image with comprehensive EXIF metadata."""
        try:
            # Get existing EXIF data
            exif = img.getexif() if hasattr(img, 'getexif') else Image.Exif()
            
            # Update fields from UI
            self.update_fields_from_ui()
            
            # Create image description with metadata
            image_description = (
                f"Date: {self.current_date}\n"
                f"Subject: {self.subject}\n"
                f"Artist: {self.owner}\n"
                f"Yaw: {self.yaw_position}\n"
                f"Tilt: {self.tilt_position}\n"
                f"Forward: {self.forward_position}\n"
                f"Project: {self.project_name}\n"
                f"Subject ID: {self.subject_id}\n"
                f"Scale: {self.scale}\n"
                f"Software: {self.software}\n"
                f"Copyright: {self.copyright}\n"
                f"Notes: {self.notes}"
            )
            
            # Add standard EXIF tags
            exif[0x010e] = image_description.encode('ascii', 'replace')  # ImageDescription
            exif[0x013b] = self.owner.encode('ascii', 'replace')  # Artist
            if self.copyright:
                exif[0x8298] = self.copyright.encode('ascii', 'replace')  # Copyright
            exif[0x0131] = self.software.encode('ascii', 'replace')  # Software
            exif[0x0132] = self.current_date  # DateTime
            exif[0x9003] = self.current_date  # DateTimeOriginal
            exif[0x9004] = self.current_date  # DateTimeDigitized

            # First save with EXIF data
            img.save(filename, 'JPEG', exif=exif, quality=100)
            
            # Now create and save thumbnail separately
            thumb_filename = filename.replace('.jpg', '_thumb.jpg')
            thumb = img.copy()
            thumb.thumbnail((160, 120), Image.LANCZOS)
            thumb.save(thumb_filename, 'JPEG', quality=85)
            
            # Show original image
            img.show()
            
            logger.debug("Image saved with EXIF data and displayed")
            return True
        
        except Exception as e:
            logger.error(f"Error saving image with EXIF data: {e}")
            return False

    def update_fields_from_ui(self) -> None:
        """Update instance variables from UI inputs."""
        try:
            # Just update the instance variables without saving
            self.subject = self.query_one("#subject_input").value
            self.owner = self.query_one("#owner_input").value
            self.project_name = self.query_one("#project_input").value
            self.subject_id = self.query_one("#subject_id_input").value
            self.scale = self.query_one("#scale_input").value
            self.software = self.query_one("#software_input").value
            self.copyright = self.query_one("#copyright_input").value
            self.notes = self.query_one("#notes_input").value
            
        except Exception as e:
            logger.error(f"Error updating fields from UI: {e}")
