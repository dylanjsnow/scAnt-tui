import os
import subprocess
import time
import asyncio
from asyncio.subprocess import create_subprocess_exec, PIPE
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid, ScrollableContainer, Container
from textual.widgets import Button, Label, Select, Static, Input, TextArea
from textual.reactive import reactive
from textual import work
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ExifTags
import json
import re
from settings import SettingsManager
from pathlib import Path
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class CameraManager(Static):
    """A widget to manage camera operations."""
    
    status = reactive("Ready")
    
    def __init__(self, id: str = "camera_manager", settings_manager=None):
        """Initialize the camera manager."""
        # Keep the super() call to properly initialize the parent widget
        super().__init__(id=id)
        
        self.cameras = []
        self.selected_camera = None
        self.current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.subject = "Scan"
        self.owner = "User"
        self.detail = "yaw0_tilt0_forward0"
        self._date_timer = None
        self.exif_display_visible = False
        
        # Store reference to settings manager
        self.settings_manager = settings_manager
        
        # EXIF display format (True for string, False for binary)
        self.exif_string_format = True
        
        # Default values for metadata fields
        self.project_name = ""
        self.subject_id = ""
        self.scale = ""
        self.copyright = ""
        self.notes = ""
        self.software = "MacroScans v1.0"
        
        # Default EXIF metadata
        self.exif_data = {
            'Make': 'Scanner3D',
            'Model': 'ScannerApp',
            'Software': self.software,
            'Orientation': 1,  # top-left
            'DateTime': datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
            'YCbCrPositioning': 1,  # centered
            'XResolution': (72, 1),
            'YResolution': (72, 1),
            'ResolutionUnit': 2,  # inches
            'ExposureTime': (1, 100),  # 1/100 second
            'FNumber': (40, 10),  # f/4.0
            'ExposureProgram': 1,  # Manual
            'ExifVersion': b'0231',
            'DateTimeOriginal': datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
            'DateTimeDigitized': datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
            'ComponentsConfiguration': b'\x01\x02\x03\x00',  # YCbCr
            'CompressedBitsPerPixel': (4, 1),
            'ExposureBiasValue': (0, 1),
            'MaxApertureValue': (20, 10),
            'MeteringMode': 5,  # Pattern
            'Flash': 16,  # No flash
            'FocalLength': (200, 10),  # 20mm
            'MakerNote': b'',
            'FlashpixVersion': b'0100',
            'ColorSpace': 1,  # sRGB
            'PixelXDimension': 1280,
            'PixelYDimension': 720,
            'FileSource': b'\x03',  # DSC
            'InteroperabilityIndex': 'R98',
            'InteroperabilityVersion': b'0100',
        }
        
        # Load settings if available
        self.load_settings()
        
        logger.info("Initializing CameraManager")
        try:
            # Your initialization code...
            pass
        except Exception as e:
            logger.error(f"Error initializing CameraManager: {e}")
    
    def load_settings(self) -> None:
        """Load camera settings from settings manager."""
        if self.settings_manager and hasattr(self.settings_manager, 'settings'):
            if 'camera' in self.settings_manager.settings:
                camera_settings = self.settings_manager.settings['camera']
                
                # Load user metadata
                self.subject = camera_settings.get("subject", self.subject)
                self.owner = camera_settings.get("owner", self.owner)
                self.detail = camera_settings.get("detail", self.detail)
                self.project_name = camera_settings.get("project_name", self.project_name)
                self.subject_id = camera_settings.get("subject_id", self.subject_id)
                self.scale = camera_settings.get("scale", self.scale)
                self.copyright = camera_settings.get("copyright", self.copyright)
                self.notes = camera_settings.get("notes", self.notes)
                self.software = camera_settings.get("software", self.software)
                self.selected_camera = camera_settings.get("selected_camera", self.selected_camera)
                
                # Try to load EXIF data from exif.json if it exists
                try:
                    exif_file = Path(__file__).parent / "exif.json"
                    if exif_file.exists():
                        with open(exif_file, 'r') as f:
                            self.exif_data = json.load(f)
                        logger.debug("Loaded EXIF data from exif.json")
                except Exception as e:
                    logger.debug(f"Error loading EXIF data: {e}")
            logger.debug("Loading camera settings")
    
    def save_settings(self) -> None:
        """Save camera settings to the settings manager."""
        if self.settings_manager and hasattr(self.settings_manager, 'settings'):
            try:
                # Create settings dictionary with current instance values
                camera_settings = {
                    "subject": self.subject,
                    "owner": self.owner,
                    "detail": self.detail,
                    "project_name": self.project_name,
                    "subject_id": self.subject_id,
                    "scale": self.scale,
                    "copyright": self.copyright,
                    "notes": self.notes,
                    "software": self.software,
                    "selected_camera": self.selected_camera,
                    "exif_string_format": True,
                    "exif_data": self.exif_data
                }
                
                # Update settings directly
                self.settings_manager.settings['camera'] = camera_settings
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
                    value=self.detail,
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
    
    def format_exif_data(self) -> str:
        """Format EXIF data for display in the TextArea."""
        # Create a copy of the EXIF data that can be serialized to JSON
        display_data = {}
        for key, value in self.exif_data.items():
            # Convert binary data to hex strings for display
            if isinstance(value, bytes):
                display_data[key] = value.hex()
            # Convert tuples to strings for display
            elif isinstance(value, tuple):
                if len(value) == 2:
                    # Format rational numbers as fractions
                    display_data[key] = f"{value[0]}/{value[1]}"
                else:
                    display_data[key] = str(value)
            else:
                display_data[key] = value
        
        return json.dumps(display_data, indent=2)
    
    def update_exif_from_display(self) -> None:
        """Update EXIF data from the TextArea display."""
        try:
            exif_display = self.query_one("#exif_display", TextArea)
            display_text = exif_display.text
            
            # Parse the JSON data
            display_data = json.loads(display_text)
            
            # Update the EXIF data with the parsed values
            for key, value in display_data.items():
                if key in self.exif_data:
                    original_value = self.exif_data[key]
                    
                    # Handle different data types
                    if isinstance(original_value, bytes):
                        # Convert hex string back to bytes
                        try:
                            self.exif_data[key] = bytes.fromhex(value)
                        except ValueError:
                            # If conversion fails, keep the original value
                            pass
                    elif isinstance(original_value, tuple):
                        # Convert fraction string back to tuple
                        if '/' in value:
                            try:
                                num, denom = value.split('/')
                                self.exif_data[key] = (int(num), int(denom))
                            except ValueError:
                                # If conversion fails, keep the original value
                                pass
                    elif isinstance(original_value, int):
                        try:
                            self.exif_data[key] = int(value)
                        except ValueError:
                            # If conversion fails, keep the original value
                            pass
                    else:
                        # For strings and other simple types
                        self.exif_data[key] = value
            
            self.status = "EXIF data updated from editor"
        except json.JSONDecodeError:
            self.status = "Error: Invalid JSON in EXIF editor"
        except Exception as e:
            self.status = f"Error updating EXIF data: {str(e)}"
    
    def update_date_field(self) -> None:
        """Update the date field with current timestamp in EXIF format (YYYY:MM:DD HH:MM:SS)."""
        try:
            # Format date according to EXIF standard
            self.current_date = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
            date_input = self.query_one("#date_input")
            if date_input:
                date_input.value = self.current_date
                
                # Also update EXIF date fields with same format
                self.exif_data.update({
                    'DateTime': self.current_date,
                    'DateTimeOriginal': self.current_date,
                    'DateTimeDigitized': self.current_date
                })
        except Exception as e:
            logger.error(f"Error updating date field: {e}")
    
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
            self.take_photo()
        elif event.button.id == "update_exif_btn":
            self.extract_camera_exif()
    
    def toggle_exif_format(self):
        """Toggle between string and binary representation of EXIF data."""
        self.exif_string_format = not self.exif_string_format
        
        # Update the button text
        toggle_btn = self.query_one("#toggle_exif_format_btn", Button)
        toggle_btn.label = f"Show {'String' if not self.exif_string_format else 'Binary'} Format"
        
        # Display the current EXIF data in the selected format
        self.display_exif_data()
    
    def display_exif_data(self):
        """Display the current EXIF data in the selected format."""
        exif_status = self.query_one("#exif_status", Static)
        
        # Clear the current display
        exif_status.update("Current EXIF Data:")
        
        # Format and display each EXIF field
        for tag_name, value in self.exif_data.items():
            if self.exif_string_format:
                # String representation
                if isinstance(value, bytes):
                    # Convert bytes to a readable hex string
                    formatted_value = value.hex()
                    self.update_exif_status(f"{tag_name}: 0x{formatted_value} (bytes)")
                elif isinstance(value, tuple) and len(value) == 2:
                    # Format rational numbers
                    if value[1] == 1:
                        formatted_value = str(value[0])
                    else:
                        formatted_value = f"{value[0]}/{value[1]} ({value[0]/value[1]:.2f})"
                    self.update_exif_status(f"{tag_name}: {formatted_value}")
                else:
                    # Regular string representation
                    self.update_exif_status(f"{tag_name}: {value}")
            else:
                # Binary/raw representation
                self.update_exif_status(f"{tag_name}: {repr(value)}")
    
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
    
    @staticmethod
    def convert_exif_for_json(exif_data: dict) -> dict:
        """Convert EXIF data to JSON-serializable format."""
        serializable_exif = {}
        for key, value in exif_data.items():
            if isinstance(value, bytes):
                # Convert bytes to hex string
                serializable_exif[key] = value.hex()
            elif isinstance(value, tuple):
                # Convert rational numbers to string representation
                if len(value) == 2:
                    serializable_exif[key] = f"{value[0]}/{value[1]}"
                else:
                    serializable_exif[key] = str(value)
            else:
                # Convert other types to strings
                serializable_exif[key] = str(value)
        return serializable_exif

    def save_exif_data(self) -> None:
        """Save EXIF data to separate exif.json file."""
        try:
            # Convert EXIF data to serializable format
            serializable_exif = self.convert_exif_for_json(self.exif_data)
            
            # Save to exif.json
            exif_file = Path(__file__).parent / "exif.json"
            with open(exif_file, 'w') as f:
                json.dump(serializable_exif, f, indent=2)
            logger.debug(f"EXIF data saved to {exif_file}")
            
            return serializable_exif
        except Exception as e:
            logger.error(f"Error saving EXIF data: {e}")
            return None

    @work
    async def extract_camera_exif(self) -> None:
        """Extract EXIF data and save to settings."""
        if not self.selected_camera:
            logger.debug("No camera selected")
            return
        
        try:
            logger.debug(f"\nUpdating EXIF data for camera: {self.selected_camera}")
            
            # Get current values from UI
            self.subject = self.query_one("#subject_input").value
            self.owner = self.query_one("#owner_input").value  # This is now the Artist
            self.project_name = self.query_one("#project_input").value
            self.subject_id = self.query_one("#subject_id_input").value
            self.scale = self.query_one("#scale_input").value
            self.software = self.query_one("#software_input").value
            self.copyright = self.query_one("#copyright_input").value
            self.notes = self.query_one("#notes_input").value
            
            # Create comprehensive image description
            image_description = (
                f"Date: {self.current_date}\n"
                f"Subject: {self.subject}\n"
                f"Artist: {self.owner}\n"
                f"Detail: {self.detail}\n"
                f"Project: {self.project_name}\n"
                f"Subject ID: {self.subject_id}\n"
                f"Scale: {self.scale}\n"
                f"Software: {self.software}\n"
                f"Copyright: {self.copyright}\n"
                f"Notes: {self.notes}"
            )
            
            # Update EXIF data
            self.exif_data.update({
                'Make': 'Canon',  # Default manufacturer
                'Model': self.selected_camera,
                'Software': self.software,
                'Copyright': self.copyright,
                'ImageDescription': image_description,
                'Artist': self.owner,  # Set Artist from Owner field
                'DateTime': self.current_date,
                'DateTimeOriginal': self.current_date,
                'DateTimeDigitized': self.current_date
            })
            
            logger.debug("Updated EXIF fields:")
            for key, value in self.exif_data.items():
                logger.debug(f"  {key}: {value}")
            
            # Save EXIF data to separate file
            serializable_exif = self.save_exif_data()
            
            if self.settings_manager:
                # Save only camera settings (no EXIF data)
                camera_settings = {
                    "subject": self.subject,
                    "owner": self.owner,
                    "detail": self.detail,
                    "project_name": self.project_name,
                    "subject_id": self.subject_id,
                    "scale": self.scale,
                    "copyright": self.copyright,
                    "notes": self.notes,
                    "software": self.software,
                    "selected_camera": self.selected_camera
                }
                
                # Update settings
                self.settings_manager.settings['camera'] = camera_settings
                self.settings_manager.save_queue.put(self.settings_manager.settings)
                logger.debug("Camera settings saved to settings.json")
            
        except Exception as e:
            logger.error(f"Error updating EXIF data: {e}")
    
    def update_exif_status(self, message):
        """Update the EXIF status area with a message."""
        try:
            exif_status = self.query_one("#exif_status", Static)
            current_text = exif_status.renderable
            
            # If this is the first message, clear the default text
            if current_text == "EXIF data will be shown here when extracted":
                current_text = ""
            
            # Add the new message with explicit line breaks
            # Static widget will respect \n characters
            if current_text:
                current_text += f"\n{message}"
            else:
                current_text = message
            
            # Update the display
            exif_status.update(current_text)
        except Exception as e:
            logger.error(f"Could not update EXIF status: {e}")
    
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
        filename = f"./results/{self.current_date}_{self.subject}_{self.owner}_{self.detail}.jpg"
        
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
            
            # Extract camera make and model for EXIF data
            make, model = self.extract_camera_info(self.selected_camera)
            self.exif_data['Make'] = make
            self.exif_data['Model'] = model
            
            result = subprocess.run(
                ["gphoto2", "--camera", self.selected_camera, "--capture-image-and-download", f"--filename={filename}"],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.status = f"Photo saved to {filename}"
                
                # Try to add EXIF data to the captured image
                try:
                    img = Image.open(filename)
                    
                    # Update pixel dimensions
                    self.exif_data['PixelXDimension'] = img.width
                    self.exif_data['PixelYDimension'] = img.height
                    
                    # Create a thumbnail
                    thumbnail_data = self.create_thumbnail(img)
                    
                    # Get EXIF dictionary
                    exif_dict = self.get_exif_dict()
                    
                    # Create EXIF data
                    exif = Image.Exif()
                    for tag, value in exif_dict.items():
                        exif[tag] = value
                    
                    # Save the image with updated EXIF data
                    img.save(filename, exif=exif)
                except Exception as e:
                    logger.error(f"Error adding EXIF data: {e}")
            else:
                self.status = f"Error capturing photo: {result.stderr}"
                # Fall back to empty image if camera capture fails
                self.take_empty_photo()
        
        except Exception as e:
            self.status = f"Error: {str(e)}"
            # Fall back to empty image if camera capture fails
            self.take_empty_photo()
            
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
            # Create EXIF data structure
            exif = Image.Exif()
            
            # Update software field from UI
            self.update_fields_from_ui()
            self.exif_data['Software'] = self.software
            
            # Add all EXIF data from our dictionary
            for tag_name, value in self.exif_data.items():
                # Find the numeric tag ID for the string tag name
                for tag_id, name in ExifTags.TAGS.items():
                    if name == tag_name:
                        exif[tag_id] = value
                        break
            
            # Add user metadata as UserComment
            user_comment = f"Detail: {self.detail}"
            if self.project_name:
                user_comment += f"\nProject: {self.project_name}"
            if self.subject_id:
                user_comment += f"\nSubject ID: {self.subject_id}"
            if self.scale:
                user_comment += f"\nScale: {self.scale}"
            if self.notes:
                user_comment += f"\nNotes: {self.notes}"
            
            # EXIF UserComment must be encoded with specific header
            encoded_comment = b'ASCII\0\0\0' + user_comment.encode('ascii', 'replace')
            
            # Find UserComment tag ID
            for tag_id, name in ExifTags.TAGS.items():
                if name == 'UserComment':
                    exif[tag_id] = encoded_comment
                    break
            
            # Add artist and copyright
            for tag_id, name in ExifTags.TAGS.items():
                if name == 'Artist':
                    exif[tag_id] = self.owner
                elif name == 'Copyright' and self.copyright:
                    exif[tag_id] = self.copyright
            
            # Save the image with EXIF data
            img.save(filename, exif=exif)
            logger.debug("Image saved with EXIF data")
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
