import os
import subprocess
import asyncio
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid, ScrollableContainer, Container
from textual.widgets import Button, Label, Select, Static, Input, TextArea
from textual.reactive import reactive
from textual import on, work
from PIL import Image,  ExifTags
import json
from pathlib import Path
import logging
from utils import CameraState, CameraMessage
from multiprocessing import Queue, Process
import shutil
import gphoto2 as gp
from current_position import CurrentPositionDisplay
from threading import Thread
import queue
from textual.message import Message

# Create logger for this module
logger = logging.getLogger(__name__)

class CameraManager(Static):
    """A widget to manage camera operations."""
    
    status = reactive("Ready")
    
    def __init__(self, position_queue: Queue, camera_photo_queue: Queue = None, settings_manager=None, id: str = "camera_manager"):
        """Initialize the camera manager."""
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
        
        # Queue for receiving position updates from stepper motors
        self.position_queue = position_queue
        
        # Use provided camera_photo_queue or create a new one
        self.camera_photo_queue = camera_photo_queue
        self.state = CameraState.IDLE
        
        # Start position update process
        self.position_process = Process(target=self._handle_position_updates, daemon=True)
        self.position_process.start()
        
        # Start photo request process
        self.photo_process = Process(target=self._handle_photo_requests, daemon=True)
        self.photo_process.start()
        
        # Default values for metadata fields
        self.project_name = ""
        self.subject_id = ""
        self.scale = ""
        self.copyright = ""
        self.notes = ""
        self.software = "scAnt-tui"

        # Load settings if available
        self.load_settings()
        
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
                # yield Button("Update EXIF Details from Camera", id="update_exif_btn", variant="default")
            
            # File naming grid
            # with Container(id="file_naming_grid"):
            # Date (auto-generated, read-only)
            with Horizontal():
                yield Label("Date:", classes="field-label")
                yield Input(
                    value=self.current_date,
                    id="date_input",
                    disabled=True
                )

            # Detail (auto-generated from stepper positions)
            with Horizontal():
                yield Label("Forward:", classes="field-label")
                yield Input(
                    value=f"{self.forward_position}",
                    id="forward_position",
                    disabled=True
                )

            # Detail (auto-generated from stepper positions)
            with Horizontal():
                yield Label("Yaw:", classes="field-label")
                yield Input(
                    value=f"{self.yaw_position}",
                    id="yaw_position",
                    disabled=True
                )

            # Detail (auto-generated from stepper positions)
            with Horizontal():
                yield Label("Tilt:", classes="field-label")
                yield Input(
                    value=f"{self.tilt_position}",
                    id="tilt_position",
                    disabled=True
                )
            
            with Horizontal():
                yield Label("Subject:", classes="field-label")
                yield Input(id="subject_input", value=self.subject)
            
            with Horizontal():
                yield Label("Artist:", classes="field-label")
                yield Input(id="owner_input", value=self.owner)
                
            
            with Horizontal():
                yield Label("Project:", classes="field-label")
                yield Input(id="project_input", value=self.project_name)
                
            with Horizontal():
                yield Label("Subject ID:", classes="field-label")
                yield Input(id="subject_id_input", value=self.subject_id)
                
            with Horizontal():
                yield Label("Scale:", classes="field-label")
                yield Input(id="scale_input", value=self.scale)
                
            with Horizontal():
                yield Label("Software:", classes="field-label")
                yield Input(id="software_input", value=self.software)
                
            with Horizontal():
                yield Label("Copyright:", classes="field-label")
                yield Input(id="copyright_input", value=self.copyright)
                
            with Horizontal():
                yield Label("Notes:", classes="field-label")
                yield Input(id="notes_input", value=self.notes)

    def on_mount(self) -> None:
        """Set up queue checking when widget is mounted."""
        self.set_interval(0.1, self.check_position_queue)
        
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
        # elif event.button.id == "update_exif_btn":
        #     logger.debug("Update EXIF Button Pressed")
        #     self.update_exif_from_camera()
    
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
            if not self.position_queue.empty():
                message_type, data = self.position_queue.get_nowait()
                
                if message_type == CameraMessage.TAKE_PHOTO:
                    if self.state == CameraState.IDLE:
                        self.state = CameraState.CAPTURING
                        # Schedule the async take_photo
                        asyncio.create_task(self.take_photo(data))
                        logger.info(f"Scheduled photo capture at position {data.get('position')}")
                    else:
                        logger.warning(f"Received photo request while camera busy (state: {self.state})")
                        # Put the message back in the queue to try again later
                        self.position_queue.put((message_type, data))
                        
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

    def take_photo_sync(self, metadata=None):
        """Non-async version of take_photo that can be called from a separate process."""
        try:
            logger.info(f"Taking photo synchronously with metadata: {metadata}")
            
            # Initialize camera
            camera = gp.Camera()
            camera.init()
            
            logger.debug("Capturing image with gphoto2...")
            
            # Capture the image
            file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
            logger.debug(f'Camera file path: {file_path.folder}/{file_path.name}')
            
            # Define target path in results directory
            os.makedirs("./results", exist_ok=True)
            
            # Generate final filename with timestamp and metadata
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            position = metadata.get('position', '0') if metadata else '0'
            axis = metadata.get('axis', 'test') if metadata else 'test'
            final_filename = f"{timestamp}_{self.subject}_{position}_{axis}.jpg"
            final_path = os.path.join("./results", final_filename)
            
            # Copy image from camera to computer
            logger.debug(f'Copying image to: {final_path}')
            camera_file = camera.file_get(
                file_path.folder, 
                file_path.name, 
                gp.GP_FILE_TYPE_NORMAL
            )
            camera_file.save(final_path)
            
            # Clean up
            camera.exit()
            
            logger.info(f"Photo saved to: {final_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error taking photo synchronously: {e}")
            return False

    def on_unmount(self) -> None:
        """Handle unmount event."""
        # Terminate the position update process
        if hasattr(self, 'position_process'):
            self.position_process.terminate()
            self.position_process.join()
        
        # Terminate the photo request process
        if hasattr(self, 'photo_process'):
            self.photo_process.terminate()
            self.photo_process.join()
        
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
            # thumb_filename = filename.replace('.jpg', '_thumb.jpg')
            # thumb = img.copy()
            # thumb.thumbnail((160, 120), Image.LANCZOS)
            # thumb.save(thumb_filename, 'JPEG', quality=85)
            
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

    def check_position_queue(self) -> None:
        """Check queue for position updates."""
        try:
            if not self.position_queue.empty():
                message = self.position_queue.get_nowait()
                
                if isinstance(message, dict):
                    # Update positions based on message type
                    if 'axis' in message and 'position' in message:
                        position = str(message['position'])
                        
                        if message['axis'] == 'Yaw':
                            self.yaw_position = position
                        elif message['axis'] == 'Tilt':
                            self.tilt_position = position
                        elif message['axis'] == 'Forward':
                            self.forward_position = position
                            
                        logger.debug(f"Updated {message['axis']} position to {position}")
                        self.update_position_widgets()
                
        except Exception as e:
            logger.error(f"Error checking position queue: {e}")

    def _handle_position_updates(self) -> None:
        """Check for position updates from the queue"""
        try:
            if not hasattr(self, 'position_queue') or self.position_queue is None:
                return
            
            # Check if there are any position updates in the queue
            if not self.position_queue.empty():
                try:
                    # Get the update from the queue
                    update = self.position_queue.get_nowait()
                    
                    # Handle different types of updates
                    if isinstance(update, dict) and 'axis' in update and 'position' in update:
                        # Position update
                        axis = update['axis']
                        position = update['position']
                        
                        # Update the appropriate position
                        if axis == "Forward":
                            self.forward_position = position
                            logger.debug(f"Updated Forward position to {position}")
                        elif axis == "Yaw":
                            self.yaw_position = position
                            logger.debug(f"Updated Yaw position to {position}")
                        elif axis == "Tilt":
                            self.tilt_position = position
                            logger.debug(f"Updated Tilt position to {position}")
                        
                        # Update the UI widgets
                        self.update_position_widgets()
                        
                    # elif isinstance(update, tuple) and len(update) == 2:
                    #     # Message tuple (type, data)
                    #     message_type, message_data = update
                        
                    #     # Handle different message types
                    #     if message_type == CameraMessage.TAKE_PHOTO:
                    #         # Take a photo
                    #         self.take_photo()
                            
                except queue.Empty:
                    # Queue was empty, that's fine
                    pass
                
        except Exception as e:
            logger.error(f"Error checking position queue: {e}")

    def update_position_widgets(self) -> None:
        """Update the position widgets with current values"""
        try:
            # Update the position input fields - use the correct IDs
            forward_input = self.query_one("#forward_position", Input)
            yaw_input = self.query_one("#yaw_position", Input)
            tilt_input = self.query_one("#tilt_position", Input)
            
            # Set the values
            forward_input.value = str(self.forward_position)
            yaw_input.value = str(self.yaw_position)
            tilt_input.value = str(self.tilt_position)
            
        except Exception as e:
            logger.error(f"Error updating position widgets: {e}")

    def _handle_photo_requests(self):
        """Process that handles photo requests from the queue"""
        while True:
            try:
                # This will block until a message is available
                message = self.camera_photo_queue.get()
                
                if isinstance(message, dict):
                    # Print out the contents of the message
                    logger.info(f"Received photo request: {message}")
                    
                    # Extract message data
                    position = message.get('position', 'unknown')
                    axis = message.get('axis', 'unknown')
                    
                    logger.info(f"Photo requested at position {position} on {axis} axis")
                    
                    # Call the synchronous version of take_photo
                    success = self.take_photo_sync(message)
                    if success:
                        logger.info(f"Successfully took photo at position {position}")
                    else:
                        logger.error(f"Failed to take photo at position {position}")
                
            except Exception as e:
                logger.error(f"Error handling photo request: {e}")

    # @on(Button.Pressed, "#take_photo_btn")
    # def on_take_photo_button_pressed(self, event: Button.Pressed) -> None:
    #     """Handle take photo button press."""
    #     try:
    #         logger.info("Take photo button pressed")
            
    #         # Instead of directly calling take_photo, add a command to the queue
    #         self.photo_command_queue.put({
    #             'command': 'take_photo',
    #             'position': f"{self.forward_position}",
    #             'axis': 'Manual'
    #         })
    #         logger.info("Added manual photo command to queue")
            
    #     except Exception as e:
    #         logger.error(f"Error handling take photo button: {e}")
