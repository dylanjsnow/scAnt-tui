import os
import json
import logging
from datetime import datetime
from pathlib import Path
from PIL import Image, ExifTags
import re
import subprocess
from asyncio.subprocess import create_subprocess_exec, PIPE
from textual import work

# Create logger for this module
logger = logging.getLogger(__name__)

class ExifManager:
    """Manages EXIF data operations for camera images."""
    
    def __init__(self):
        """Initialize the EXIF manager."""
        self.exif_data = {
            'Make': 'Scanner3D',
            'Model': 'ScannerApp',
            'Software': 'MacroScans v1.0',
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
        self.load_exif_data()

    def load_exif_data(self) -> None:
        """Load EXIF data from file if it exists."""
        try:
            exif_file = Path(__file__).parent / "exif.json"
            if exif_file.exists():
                with open(exif_file, 'r') as f:
                    self.exif_data.update(json.load(f))
                logger.debug("Loaded EXIF data from exif.json")
        except Exception as e:
            logger.error(f"Error loading EXIF data: {e}")

    def save_exif_data(self) -> None:
        """Save current EXIF data to file."""
        try:
            exif_file = Path(__file__).parent / "exif.json"
            with open(exif_file, 'w') as f:
                json.dump(self.exif_data, f, indent=2)
            logger.debug(f"EXIF data saved to {exif_file}")
        except Exception as e:
            logger.error(f"Error saving EXIF data: {e}")

    def update_exif_data(self, metadata: dict) -> None:
        """Update EXIF data with new metadata."""
        try:
            # Create comprehensive image description
            image_description = (
                f"Date: {metadata.get('date', '')}\n"
                f"Subject: {metadata.get('subject', '')}\n"
                f"Artist: {metadata.get('artist', '')}\n"
                f"Detail: {metadata.get('detail', '')}\n"
                f"Project: {metadata.get('project_name', '')}\n"
                f"Subject ID: {metadata.get('subject_id', '')}\n"
                f"Scale: {metadata.get('scale', '')}\n"
                f"Software: {metadata.get('software', '')}\n"
                f"Copyright: {metadata.get('copyright', '')}\n"
                f"Notes: {metadata.get('notes', '')}"
            )
            
            # Update EXIF data
            self.exif_data.update({
                'Make': metadata.get('make', 'Canon'),
                'Model': metadata.get('model', ''),
                'Software': metadata.get('software', ''),
                'Copyright': metadata.get('copyright', ''),
                'ImageDescription': image_description,
                'Artist': metadata.get('artist', ''),
                'DateTime': metadata.get('date', ''),
                'DateTimeOriginal': metadata.get('date', ''),
                'DateTimeDigitized': metadata.get('date', '')
            })
            
            # Save updated EXIF data
            self.save_exif_data()
            
        except Exception as e:
            logger.error(f"Error updating EXIF data: {e}")

    def save_image_with_exif(self, img: Image, filename: str) -> bool:
        """Save an image with EXIF metadata."""
        try:
            # Create EXIF data structure
            exif = Image.Exif()
            
            # Add all EXIF data from our dictionary
            for tag_name, value in self.exif_data.items():
                # Find the numeric tag ID for the string tag name
                for tag_id, name in ExifTags.TAGS.items():
                    if name == tag_name:
                        exif[tag_id] = value
                        break
            
            # Save the image with EXIF data
            img.save(filename, exif=exif)
            logger.debug("Image saved with EXIF data")
            return True
            
        except Exception as e:
            logger.error(f"Error saving image with EXIF data: {e}")
            return False

    def extract_camera_info(self, camera_name: str) -> tuple:
        """Extract make and model from camera name."""
        try:
            # Split on first space to separate make and model
            parts = camera_name.split(' ', 1)
            if len(parts) == 2:
                return parts[0], parts[1]
            return camera_name, ''  # Return full name as make if no space found
        except Exception as e:
            logger.error(f"Error extracting camera info: {e}")
            return 'Unknown', 'Unknown'

    async def get_camera_exif(self, camera_name: str) -> dict:
        """Get EXIF data from camera."""
        try:
            # Run gphoto2 command to get camera config
            process = await create_subprocess_exec(
                'gphoto2',
                '--camera', camera_name,
                '--list-config',
                stdout=PIPE,
                stderr=PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.error(f"Error getting camera config: {stderr.decode()}")
                return {}

            # Parse the output to get relevant EXIF data
            config_data = stdout.decode().splitlines()
            exif_data = {}
            
            for line in config_data:
                if '/main/' in line:
                    # Extract parameter name
                    param = line.split('/')[-1]
                    
                    # Get parameter value
                    value_process = await create_subprocess_exec(
                        'gphoto2',
                        '--camera', camera_name,
                        '--get-config', param,
                        stdout=PIPE,
                        stderr=PIPE
                    )
                    value_stdout, value_stderr = await value_process.communicate()
                    
                    if value_process.returncode == 0:
                        value = self._parse_config_value(value_stdout.decode())
                        if value:
                            exif_data[param] = value

            # Extract make and model
            make, model = self.extract_camera_info(camera_name)
            exif_data.update({
                'Make': make,
                'Model': model
            })

            return exif_data

        except Exception as e:
            logger.error(f"Error getting camera EXIF: {e}")
            return {}

    def _parse_config_value(self, config_output: str) -> str:
        """Parse gphoto2 config output to get current value."""
        try:
            # Look for "Current:" line
            for line in config_output.splitlines():
                if 'Current:' in line:
                    return line.split('Current:', 1)[1].strip()
            return ""
        except Exception as e:
            logger.error(f"Error parsing config value: {e}")
            return ""

    def convert_to_exif_format(self, value: str) -> str:
        """Convert a value to EXIF-compatible format."""
        try:
            # Remove any non-alphanumeric characters except spaces and basic punctuation
            cleaned = re.sub(r'[^\w\s\-\.,:]', '', value)
            # Truncate to reasonable length if needed
            return cleaned[:256]
        except Exception as e:
            logger.error(f"Error converting to EXIF format: {e}")
            return ""

    def format_exif_value(self, value) -> str:
        """Format an EXIF value for display."""
        if isinstance(value, bytes):
            try:
                # Try to decode as ASCII first
                return value.decode('ascii')
            except:
                # If that fails, return hex representation
                return value.hex()
        elif isinstance(value, tuple):
            # Format rational numbers
            if len(value) == 2:
                return f"{value[0]}/{value[1]}"
        return str(value)

    def get_formatted_exif_data(self) -> dict:
        """Get EXIF data with all values formatted as strings."""
        return {k: self.format_exif_value(v) for k, v in self.exif_data.items()} 
    
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
                self.settings_manager.save_all()
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