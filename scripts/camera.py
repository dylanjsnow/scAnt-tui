import os
import subprocess
import time
import asyncio
from asyncio.subprocess import create_subprocess_exec, PIPE
from datetime import datetime
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, Grid, ScrollableContainer
from textual.widgets import Button, Label, Select, Static, Input, TextArea
from textual.reactive import reactive
from textual import work
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ExifTags
import json
import re
from settings import SettingsManager

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
    
    def load_settings(self):
        """Load camera settings from the settings manager."""
        if self.settings_manager and hasattr(self.settings_manager, 'settings'):
            # Check if camera section exists in settings
            if 'camera' in self.settings_manager.settings:
                camera_settings = self.settings_manager.settings['camera']
                
                # Load user metadata with defaults
                self.subject = camera_settings.get("subject", self.subject)
                self.owner = camera_settings.get("owner", self.owner)
                self.detail = camera_settings.get("detail", self.detail)
                self.project_name = camera_settings.get("project_name", self.project_name)
                self.subject_id = camera_settings.get("subject_id", self.subject_id)
                self.scale = camera_settings.get("scale", self.scale)
                self.copyright = camera_settings.get("copyright", self.copyright)
                self.notes = camera_settings.get("notes", self.notes)
                self.software = camera_settings.get("software", self.software)
                
                # Load last selected camera
                self.selected_camera = camera_settings.get("selected_camera", self.selected_camera)
                
                # Load EXIF display preferences
                self.exif_string_format = camera_settings.get("exif_string_format", self.exif_string_format)
                
                # Load EXIF data if available
                if "exif_data" in camera_settings:
                    saved_exif = camera_settings["exif_data"]
                    # Update our EXIF data with saved values
                    for key, value in saved_exif.items():
                        self.exif_data[key] = value
    
    def save_settings(self):
        """Save camera settings to the settings manager."""
        if self.settings_manager and hasattr(self.settings_manager, 'settings'):
            try:
                # Update fields from UI before saving
                self.update_fields_from_ui()
                
                # Prepare camera settings
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
                    "exif_string_format": self.exif_string_format,
                }
                
                # Save EXIF data that can be serialized
                serializable_exif = {}
                for key, value in self.exif_data.items():
                    # Skip binary data for now (would need special handling)
                    if not isinstance(value, bytes):
                        serializable_exif[key] = value
                
                camera_settings["exif_data"] = serializable_exif
                
                # Update the settings
                if 'camera' not in self.settings_manager.settings:
                    self.settings_manager.settings['camera'] = {}
                
                # Update the camera section
                self.settings_manager.settings['camera'].update(camera_settings)
                
                # Save the settings
                if hasattr(self.settings_manager, 'save_settings'):
                    self.settings_manager.save_settings()
            except Exception as e:
                print(f"Error saving camera settings: {e}")
    
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
            
            # File naming and metadata options
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
                
                # Project Name (user input)
                yield Label("Project:", classes="field-label")
                yield Input(
                    value=self.project_name,
                    id="project_input",
                    placeholder="Enter project name",
                    classes="field-input"
                )
                
                # Subject ID (user input)
                yield Label("Subject ID:", classes="field-label")
                yield Input(
                    value=self.subject_id,
                    id="subject_id_input",
                    placeholder="Enter subject ID",
                    classes="field-input"
                )
                
                # Scale/Magnification (user input)
                yield Label("Scale:", classes="field-label")
                yield Input(
                    value=self.scale,
                    id="scale_input",
                    placeholder="Enter scale/magnification",
                    classes="field-input"
                )
                
                # Software name (user input)
                yield Label("Software:", classes="field-label")
                yield Input(
                    value=self.software,
                    id="software_input",
                    placeholder="Enter software name",
                    classes="field-input"
                )
                
                # Copyright (user input)
                yield Label("Copyright:", classes="field-label")
                yield Input(
                    value=self.copyright,
                    id="copyright_input",
                    placeholder="Enter copyright info",
                    classes="field-input"
                )
                
                # Notes (user input)
                yield Label("Notes:", classes="field-label")
                yield Input(
                    value=self.notes,
                    id="notes_input",
                    placeholder="Enter additional notes",
                    classes="field-input"
                )
            
            # EXIF data controls
            with Horizontal(id="exif_controls", classes="control-row"):
                yield Button("Update Details from Camera", id="update_exif_btn", variant="primary", classes="action-button")
                yield Button("Toggle EXIF Format", id="toggle_exif_format_btn", variant="default", classes="action-button")
            
            # EXIF extraction status - using a TextArea instead of a Label for better scrolling
            with Vertical(id="exif_status_container", classes="status-container"):
                yield Label("EXIF Data", id="exif_status_title", classes="section-title")
                yield Static("EXIF data will be shown here when extracted", id="exif_status", classes="exif-status")
            
            # Camera control buttons
            with Horizontal(id="camera_controls", classes="control-row"):
                yield Button("Take Photo", id="take_photo_btn", variant="primary", classes="action-button")
            
            # Status display
            with Horizontal(id="camera_status_area", classes="status-row"):
                yield Label(self.status, id="camera_status", classes="status-label")
    
    def on_mount(self) -> None:
        """Event handler called when widget is added to the app"""
        # Load settings first
        self.load_settings()
        # Schedule widget updates for after compose
        self.set_timer(0.2, self.update_widget_values)
        
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
            print(f"Error updating fields from UI: {e}")
    
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
        """Update the date field with current timestamp."""
        self.current_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_input = self.query_one("#date_input", Input)
        date_input.value = self.current_date
        
        # Also update EXIF date fields
        now = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
        self.exif_data['DateTime'] = now
        self.exif_data['DateTimeOriginal'] = now
        self.exif_data['DateTimeDigitized'] = now
    
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
        # Save settings when user edits metadata fields
        if event.input.id in ["subject_input", "owner_input", "project_input", 
                             "subject_id_input", "scale_input", "software_input",
                             "copyright_input", "notes_input"]:
            # Fix the lambda to accept the event argument
            self.app.call_later(lambda _: self.save_settings(), 1)
    
    def on_select_changed(self, event: Select.Changed) -> None:
        """Handle select change events."""
        if event.select.id == "camera_select":
            self.selected_camera = event.value
            self.status = f"Selected camera: {self.selected_camera}"
            # Save the selected camera
            self.save_settings()
    
    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events."""
        button_id = event.button.id
        
        if button_id == "take_photo_btn":
            self.take_photo()
        elif button_id == "update_exif_btn":
            self.extract_camera_exif()
        elif button_id == "toggle_exif_format_btn":
            self.toggle_exif_format()
    
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
    async def extract_camera_exif(self) -> None:
        """Extract EXIF data from the selected camera."""
        if not self.selected_camera:
            self.status = "No camera selected"
            return
        
        self.status = "Extracting camera details..."
        
        # Clear the EXIF status area
        exif_status = self.query_one("#exif_status", Static)
        exif_status.update("Starting EXIF extraction...")
        
        print(f"Starting EXIF extraction for camera: {self.selected_camera}")
        
        try:
            # Run gphoto2 command to get camera summary
            print("Getting camera summary...")
            self.status = "Getting camera summary..."
            self.update_exif_status("Getting camera summary...")
            
            # Create and run the process
            process = await create_subprocess_exec(
                "gphoto2", "--camera", self.selected_camera, "--summary",
                stdout=PIPE, stderr=PIPE
            )
            
            # Wait for the process to complete and get output
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                summary = stdout.decode('utf-8')
                print(f"Camera summary received: {len(summary)} bytes")
                
                # Extract camera make and model
                make_match = re.search(r"Manufacturer:\s*([^\n]+)", summary)
                model_match = re.search(r"Model:\s*([^\n]+)", summary)
                
                if make_match:
                    self.exif_data['Make'] = make_match.group(1).strip()
                    print(f"Extracted camera make: {self.exif_data['Make']}")
                    self.update_exif_status(f"Make: {self.exif_data['Make']}")
                    
                if model_match:
                    self.exif_data['Model'] = model_match.group(1).strip()
                    print(f"Extracted camera model: {self.exif_data['Model']}")
                    self.update_exif_status(f"Model: {self.exif_data['Model']}")
                
                # Try to get camera configuration for more detailed EXIF data
                print("Getting camera configuration list...")
                self.status = "Getting camera configuration..."
                self.update_exif_status("Getting camera configuration...")
                
                # Run the list-config command asynchronously
                config_process = await create_subprocess_exec(
                    "gphoto2", "--camera", self.selected_camera, "--list-config",
                    stdout=PIPE, stderr=PIPE
                )
                
                config_stdout, config_stderr = await config_process.communicate()
                
                if config_process.returncode == 0:
                    config_list = config_stdout.decode('utf-8').strip().split('\n')
                    print(f"Found {len(config_list)} configuration items")
                    self.update_exif_status(f"Found {len(config_list)} configuration items")
                    
                    # Extract specific configuration values that map to EXIF data
                    config_count = 0
                    for config_item in config_list:
                        if "/main/" not in config_item:
                            continue
                            
                        config_count += 1
                        print(f"Processing config item {config_count}/{len(config_list)}: {config_item}")
                        self.status = f"Processing config: {config_item}"
                        self.update_exif_status(f"Processing: {config_item}")
                        
                        # Get the value for this configuration item asynchronously
                        get_config_process = await create_subprocess_exec(
                            "gphoto2", "--camera", self.selected_camera, "--get-config", config_item,
                            stdout=PIPE, stderr=PIPE
                        )
                        
                        get_config_stdout, get_config_stderr = await get_config_process.communicate()
                        
                        if get_config_process.returncode == 0:
                            config_value = get_config_stdout.decode('utf-8')
                            
                            # Print both the length and a preview of the actual content
                            value_preview = config_value[:100] + "..." if len(config_value) > 100 else config_value
                            value_preview = value_preview.replace('\n', '\\n')
                            print(f"Got config value for {config_item}: {len(config_value)} bytes")
                            print(f"Value content: {value_preview}")
                            
                            # Try to extract the current value
                            current_value_match = re.search(r"Current:\s*([^\n]+)", config_value)
                            if current_value_match:
                                current_value = current_value_match.group(1).strip()
                                print(f"Current value: {current_value}")
                                
                                # Map camera configuration to EXIF data
                                if "shutterspeed" in config_item.lower() or "exposuretime" in config_item.lower():
                                    try:
                                        # Try to parse as a fraction (e.g., "1/100")
                                        if "/" in current_value:
                                            num, denom = current_value.split("/")
                                            self.exif_data['ExposureTime'] = (int(num), int(denom))
                                            self.update_exif_status(f"ExposureTime: {current_value}")
                                    except (ValueError, IndexError):
                                        print(f"Could not parse exposure time: {current_value}")
                                
                                elif "aperture" in config_item.lower() or "fnumber" in config_item.lower():
                                    try:
                                        aperture_value = current_value
                                        if aperture_value.startswith("f/"):
                                            aperture_value = aperture_value[2:]
                                        self.exif_data['FNumber'] = (int(float(aperture_value) * 10), 10)
                                        self.update_exif_status(f"FNumber: {current_value}")
                                    except (ValueError, IndexError):
                                        print(f"Could not parse aperture: {current_value}")
                                
                                elif "iso" in config_item.lower():
                                    try:
                                        iso_value = int(current_value)
                                        self.exif_data['ISOSpeedRatings'] = iso_value
                                        self.update_exif_status(f"ISO: {current_value}")
                                    except (ValueError, IndexError):
                                        print(f"Could not parse ISO: {current_value}")
                                
                                elif "focallength" in config_item.lower():
                                    try:
                                        focal_value = current_value
                                        if "mm" in focal_value:
                                            focal_value = focal_value.replace("mm", "").strip()
                                        self.exif_data['FocalLength'] = (int(float(focal_value) * 10), 10)
                                        self.update_exif_status(f"FocalLength: {current_value}")
                                    except (ValueError, IndexError):
                                        print(f"Could not parse focal length: {current_value}")
                                
                                elif "meteringmode" in config_item.lower():
                                    # Map camera metering mode to EXIF metering mode
                                    metering_map = {
                                        "Evaluative": 5,  # Pattern
                                        "Center-weighted": 2,  # Center-weighted average
                                        "Spot": 3,  # Spot
                                        "Partial": 6,  # Partial
                                    }
                                    if current_value in metering_map:
                                        self.exif_data['MeteringMode'] = metering_map[current_value]
                                        self.update_exif_status(f"MeteringMode: {current_value}")
                                
                                elif "colorspace" in config_item.lower():
                                    # Map camera color space to EXIF color space
                                    if current_value == "sRGB":
                                        self.exif_data['ColorSpace'] = 1
                                    elif current_value == "Adobe RGB":
                                        self.exif_data['ColorSpace'] = 2
                                    self.update_exif_status(f"ColorSpace: {current_value}")
                
                    print(f"Processed {config_count} configuration items")
                    self.status = "Camera details updated"
                    self.update_exif_status("EXIF data extraction complete")
                else:
                    error_msg = f"Error getting camera configuration: {config_stderr.decode('utf-8')}"
                    print(error_msg)
                    self.status = error_msg
                    self.update_exif_status(error_msg)
            else:
                error_msg = f"Error getting camera summary: {stderr.decode('utf-8')}"
                print(error_msg)
                self.status = error_msg
                self.update_exif_status(error_msg)
        
        except Exception as e:
            error_msg = f"Error extracting camera details: {str(e)}"
            print(f"Exception in extract_camera_exif: {error_msg}")
            self.status = error_msg
            self.update_exif_status(error_msg)
        
        print("EXIF extraction completed")

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
            print(f"Could not update EXIF status: {e}")
    
    def update_input_field(self, field_id, value):
        """Safely update an input field if it exists."""
        try:
            input_field = self.query_one(f"#{field_id}", Input)
            input_field.value = str(value)
        except Exception as e:
            print(f"Could not update field {field_id}: {e}")
    
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
        """Create an empty image with text indicating no camera was connected."""
        try:
            # Create a blank image with gray background
            width, height = 1280, 720
            img = Image.new('RGB', (width, height), color=(200, 200, 200))
            draw = ImageDraw.Draw(img)
            
            # Add text to the image
            text = "No camera connected"
            text_position = (width // 2, height // 2)
            
            # Try to use a system font, fall back to default if not available
            try:
                font = ImageFont.truetype("Arial", 36)
            except IOError:
                font = ImageFont.load_default()
            
            # Calculate text size to center it
            text_width = draw.textlength(text, font=font)
            text_position = (width // 2 - text_width // 2, height // 2 - 18)
            
            # Draw the text
            draw.text(text_position, text, fill=(0, 0, 0), font=font)
            
            # Add metadata text
            metadata_text = f"Date: {self.current_date}\nSubject: {self.subject}\nOwner: {self.owner}\nDetail: {self.detail}"
            metadata_position = (20, height - 100)
            draw.text(metadata_position, metadata_text, fill=(0, 0, 0), font=font)
            
            # Update pixel dimensions
            self.pixel_x_dimension = str(width)
            self.pixel_y_dimension = str(height)
            
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
            
            print(f"Created empty image: {filename}")
            return True
        except Exception as e:
            print(f"Error creating empty image: {e}")
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
                    print(f"Error adding EXIF data: {e}")
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
            return True
        except Exception as e:
            print(f"Error saving image with EXIF data: {e}")
            return False

    def update_fields_from_ui(self):
        """Update instance variables from UI inputs."""
        try:
            self.subject = self.query_one("#subject_input", Input).value
            self.owner = self.query_one("#owner_input", Input).value
            self.project_name = self.query_one("#project_input", Input).value
            self.subject_id = self.query_one("#subject_id_input", Input).value
            self.scale = self.query_one("#scale_input", Input).value
            self.software = self.query_one("#software_input", Input).value
            self.copyright = self.query_one("#copyright_input", Input).value
            self.notes = self.query_one("#notes_input", Input).value
            
            # Save settings after updating fields
            self.save_settings()
        except Exception as e:
            print(f"Error updating fields from UI: {e}")
