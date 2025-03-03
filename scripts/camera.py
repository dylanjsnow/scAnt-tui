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
        self.exif_display_visible = False
        
        # Default EXIF metadata
        self.exif_data = {
            'Make': 'Scanner3D',
            'Model': 'ScannerApp',
            'Orientation': 1,  # top-left
            'Software': 'ScannerApp v1.0',
            'DateTime': datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
            'YCbCrPositioning': 1,  # centered
            'Compression': 6,  # JPEG compression
            'XResolution': (72, 1),
            'YResolution': (72, 1),
            'ResolutionUnit': 2,  # Inch
            'ExposureTime': (1, 100),  # 1/100 s
            'FNumber': (40, 10),  # f/4.0
            'ExposureProgram': 2,  # Normal program
            'ExifVersion': b'0221',  # Exif version 2.21
            'DateTimeOriginal': datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
            'DateTimeDigitized': datetime.now().strftime("%Y:%m:%d %H:%M:%S"),
            'ComponentsConfiguration': b'\x01\x02\x03\x00',  # Y Cb Cr –
            'CompressedBitsPerPixel': (401, 100),  # 4.01
            'ExposureBiasValue': (0, 10),  # 0.0
            'MaxApertureValue': (20, 10),  # 2.00
            'MeteringMode': 5,  # Pattern
            'Flash': 0,  # Flash did not fire
            'FocalLength': (201, 10),  # 20.1 mm
            'FlashpixVersion': b'0100',  # FlashPix version 1.0
            'ColorSpace': 1,  # sRGB
            'PixelXDimension': 1280,
            'PixelYDimension': 720,
            'FileSource': b'\x03',  # DSC
            'InteroperabilityIndex': 'R98',
            'InteroperabilityVersion': b'0100'
        }
        
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
            
            # EXIF data controls
            with Horizontal(id="exif_controls", classes="control-row"):
                yield Button("Update Details from Camera", id="update_exif_btn", variant="primary", classes="action-button")
            
            # Basic EXIF data fields
            with Grid(id="exif_fields_grid", classes="exif-fields-section"):
                # Camera info
                yield Label("Make:", classes="field-label")
                yield Input(value=self.exif_data.get('Make', ''), id="make_input", classes="field-input")
                
                yield Label("Model:", classes="field-label")
                yield Input(value=self.exif_data.get('Model', ''), id="model_input", classes="field-input")
                
                # Exposure info
                yield Label("Exposure Time:", classes="field-label")
                yield Input(value="1/100", id="exposure_time_input", classes="field-input")
                
                yield Label("F-Number:", classes="field-label")
                yield Input(value="4.0", id="f_number_input", classes="field-input")
                
                yield Label("Focal Length:", classes="field-label")
                yield Input(value="20.1", id="focal_length_input", classes="field-input")
            
            # Camera control buttons
            with Horizontal(id="camera_controls", classes="control-row"):
                yield Button("Take Photo", id="take_photo_btn", variant="primary", classes="action-button")
            
            # Status display
            with Horizontal(id="camera_status_area", classes="status-row"):
                yield Label(self.status, id="camera_status", classes="status-label")
    
    def on_mount(self) -> None:
        """Handle the mount event."""
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
                self.take_empty_photo()
        elif event.button.id == "update_exif_btn":
            if self.selected_camera:
                self.extract_camera_exif()
            else:
                self.status = "No camera selected for EXIF extraction"
        elif event.button.id == "toggle_exif_btn":
            self.toggle_exif_display()
    
    def toggle_exif_display(self) -> None:
        """Toggle the visibility of the EXIF data display."""
        exif_container = self.query_one("#exif_container")
        
        # Toggle visibility
        self.exif_display_visible = not self.exif_display_visible
        exif_container.display = self.exif_display_visible
        
        # If becoming visible, update the display with current EXIF data
        if self.exif_display_visible:
            exif_display = self.query_one("#exif_display", TextArea)
            exif_display.text = self.format_exif_data()
        else:
            # If becoming hidden, update EXIF data from the display
            self.update_exif_from_display()
        
        self.status = f"EXIF data display {'shown' if self.exif_display_visible else 'hidden'}"
    
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
        print(f"Starting EXIF extraction for camera: {self.selected_camera}")
        
        try:
            # Run gphoto2 command to get camera summary
            print("Getting camera summary...")
            self.status = "Getting camera summary..."
            
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
                    # Safely update UI if element exists
                    self.update_input_field("make_input", self.exif_data['Make'])
                    
                if model_match:
                    self.exif_data['Model'] = model_match.group(1).strip()
                    print(f"Extracted camera model: {self.exif_data['Model']}")
                    # Safely update UI if element exists
                    self.update_input_field("model_input", self.exif_data['Model'])
                
                # Try to get camera configuration for more detailed EXIF data
                print("Getting camera configuration list...")
                self.status = "Getting camera configuration..."
                
                # Run the list-config command asynchronously
                config_process = await create_subprocess_exec(
                    "gphoto2", "--camera", self.selected_camera, "--list-config",
                    stdout=PIPE, stderr=PIPE
                )
                
                config_stdout, config_stderr = await config_process.communicate()
                
                if config_process.returncode == 0:
                    config_list = config_stdout.decode('utf-8').strip().split('\n')
                    print(f"Found {len(config_list)} configuration items")
                    
                    # Extract specific configuration values that map to EXIF data
                    config_count = 0
                    for config_item in config_list:
                        if "/main/" not in config_item:
                            continue
                            
                        config_count += 1
                        print(f"Processing config item {config_count}/{len(config_list)}: {config_item}")
                        self.status = f"Processing config: {config_item}"
                        
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
                                
                                # For known enum types, show the human-readable interpretation
                                if "orientation" in config_item.lower():
                                    orientation_map = {
                                        "1": "top-left (normal)",
                                        "2": "top-right (mirrored)",
                                        "3": "bottom-right (180° rotation)",
                                        "4": "bottom-left (180° rotation, mirrored)",
                                        "5": "left-top (90° CCW rotation, mirrored)",
                                        "6": "right-top (90° CW rotation)",
                                        "7": "right-bottom (90° CW rotation, mirrored)",
                                        "8": "left-bottom (90° CCW rotation)"
                                    }
                                    if current_value in orientation_map:
                                        print(f"Orientation interpretation: {orientation_map[current_value]}")
                                
                                elif "meteringmode" in config_item.lower():
                                    metering_map = {
                                        "0": "Unknown",
                                        "1": "Average",
                                        "2": "Center-weighted average",
                                        "3": "Spot",
                                        "4": "Multi-spot",
                                        "5": "Pattern",
                                        "6": "Partial",
                                        "255": "Other"
                                    }
                                    if current_value in metering_map:
                                        print(f"Metering mode interpretation: {metering_map[current_value]}")
                                
                                elif "flash" in config_item.lower():
                                    flash_map = {
                                        "0": "No Flash",
                                        "1": "Fired",
                                        "5": "Fired, Return not detected",
                                        "7": "Fired, Return detected",
                                        "8": "On, Did not fire",
                                        "9": "On, Fired",
                                        "16": "Off, Did not fire",
                                        "24": "Auto, Did not fire",
                                        "25": "Auto, Fired",
                                        "32": "No flash function",
                                        "65": "Fired, Red-eye reduction",
                                        "73": "On, Red-eye reduction",
                                        "88": "Auto, Did not fire, Red-eye reduction",
                                        "89": "Auto, Fired, Red-eye reduction"
                                    }
                                    if current_value in flash_map:
                                        print(f"Flash interpretation: {flash_map[current_value]}")
                                
                                elif "colorspace" in config_item.lower():
                                    colorspace_map = {
                                        "1": "sRGB",
                                        "2": "Adobe RGB",
                                        "65535": "Uncalibrated"
                                    }
                                    if current_value in colorspace_map:
                                        print(f"Color space interpretation: {colorspace_map[current_value]}")
                
                    print(f"Processed {config_count} configuration items")
                    self.status = "Camera details updated"
                else:
                    error_msg = f"Error getting camera configuration: {config_stderr.decode('utf-8')}"
                    print(error_msg)
                    self.status = error_msg
            else:
                error_msg = f"Error getting camera summary: {stderr.decode('utf-8')}"
                print(error_msg)
                self.status = error_msg
        
        except Exception as e:
            error_msg = f"Error extracting camera details: {str(e)}"
            print(f"Exception in extract_camera_exif: {error_msg}")
            self.status = error_msg
        
        print("EXIF extraction completed")
    
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
        """Clean up when widget is removed."""
        if self._date_timer:
            self._date_timer.stop()
