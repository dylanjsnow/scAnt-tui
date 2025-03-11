from pathlib import Path
import json
import os
import time
from queue import Queue
from threading import Thread
from utils import get_axes
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

class SettingsManager:
    """Manages saving and loading of stepper motor settings"""
    
    def __init__(self, settings_file="settings.json"):
        """Initialize settings manager."""
        self.settings_file = Path(__file__).parent / settings_file
        logger.info(f"Initializing SettingsManager with file: {self.settings_file}")
        
        # Initialize with default settings
        self.settings = self._get_default_settings()
        
        # Load existing settings if available
        self.load_settings()
        logger.info("SettingsManager initialization complete")

    def _get_default_settings(self) -> dict:
        """Get default settings structure."""
        return {
            "stepper_1": {
                "usb_id": "",  # Empty string instead of None
                "current": "0",  # Convert to strings
                "speed": "0",
                "divisions": "",
                "min_position": "",
                "max_position": "",
                "current_limit": "2",
                "axis": "Forward",
                "serial": "",
                "max_speed": "1000"
            },
            "stepper_2": {
                "usb_id": "",
                "current": "0",
                "speed": "0",
                "divisions": "",
                "min_position": "",
                "max_position": "",
                "current_limit": "2",
                "axis": "Tilt",
                "serial": "",
                "max_speed": "1000"
            },
            "stepper_3": {
                "usb_id": "",
                "current": "0",
                "speed": "0",
                "divisions": "",
                "min_position": "",
                "max_position": "",
                "current_limit": "2",
                "axis": "Yaw",
                "serial": "",
                "max_speed": "1000"
            },
            "camera": {
                "selected_camera": "",
                "subject": "Scan",
                "owner": "User",
                "detail": "yaw0_tilt0_forward0",
                "project_name": "",
                "subject_id": "",
                "scale": "",
                "copyright": "",
                "notes": "",
                "software": "MacroScans v1.0"
            }
        }

    def queue_save(self, stepper_id: str, setting_type: str, value: str):
        """Queue a settings save operation"""
        stepper_key = f"stepper_{stepper_id}"
        logger.debug(f"Updating setting for {stepper_key} {setting_type}: {value}")
        
        # Ensure value is a string
        value = str(value) if value is not None else ""
        
        # Create a deep copy of current settings
        settings_copy = self.settings.copy()
        
        # Make sure the stepper section exists
        if stepper_key not in settings_copy:
            settings_copy[stepper_key] = self.settings["stepper_1"].copy()
        
        # Special handling for specific settings
        if setting_type in ["current_limit", "max_speed", "usb_id"]:
            # Ensure these values are always strings
            settings_copy[stepper_key][setting_type] = str(value)
            logger.debug(f"Updated {setting_type} to: {settings_copy[stepper_key][setting_type]}")
        else:
            settings_copy[stepper_key][setting_type] = value
        
        # Update internal settings
        self.settings = settings_copy

    def save_all(self):
        """Save all settings to file"""
        try:
            logger.info(f"Saving all settings to {self.settings_file}")
            
            # Create directory if it doesn't exist
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write to temporary file first
            temp_file = self.settings_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(self.settings, f, indent=4)
                f.flush()
                os.fsync(f.fileno())
            
            # Rename temp file to actual file (atomic operation)
            temp_file.replace(self.settings_file)
            
            logger.debug("Settings saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving settings: {e}")

    def get_setting(self, stepper_id: str, setting_type: str) -> str:
        """Get a setting value"""
        stepper_key = f"stepper_{stepper_id}"
        
        # If the stepper doesn't exist in settings, create it
        if stepper_key not in self.settings:
            self.settings[stepper_key] = self.settings["stepper_1"].copy()
        
        # Special handling for specific settings
        if setting_type in ["current_limit", "max_speed", "usb_id"]:
            value = self.settings[stepper_key].get(setting_type, "")
            # Ensure these values are always returned as strings
            return str(value) if value is not None else ""
        
        # Default handling for other settings
        value = self.settings[stepper_key].get(setting_type, "")
        return str(value) if value is not None else ""

    def load_settings(self):
        """Load settings from file, create if doesn't exist."""
        try:
            logger.info(f"Attempting to load settings from {self.settings_file}")
            if self.settings_file.exists():
                # Load and parse the settings file
                loaded_settings = self._load_settings()
                if loaded_settings:
                    logger.info("Settings file loaded successfully")
                    
                    # Update existing settings with loaded values
                    for section in self.settings:
                        if section in loaded_settings:
                            # Convert all values to strings
                            loaded_values = {
                                k: str(v) if v is not None else ""
                                for k, v in loaded_settings[section].items()
                            }
                            self.settings[section].update(loaded_values)
                    logger.debug("Settings merged with defaults")
                    
                    # Log loaded settings for debugging
                    logger.debug("Current settings after loading:")
                    logger.debug(json.dumps(self.settings, indent=2))
            else:
                logger.info("Settings file not found, creating with defaults")
                
        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            logger.info("Using default settings")

    def _load_settings(self) -> dict:
        """Load raw settings from file"""
        try:
            if self.settings_file.exists():
                logger.debug(f"Reading settings from {self.settings_file}")
                with open(self.settings_file, 'r') as f:
                    settings = json.load(f)
                    
                    # Get defaults from stepper_1 or create new defaults
                    defaults = (settings.get("stepper_1", {}) if "stepper_1" in settings 
                              else self._get_default_settings()["stepper_1"])
                    
                    # Ensure all steppers exist with proper defaults
                    for stepper in ["1", "2", "3"]:
                        stepper_key = f"stepper_{stepper}"
                        if stepper_key not in settings:
                            settings[stepper_key] = {}
                            
                        # Copy defaults for each setting if not present
                        for key, default_value in defaults.items():
                            if key not in settings[stepper_key] or not settings[stepper_key][key]:
                                if key == "axis":
                                    # Special handling for axis - use corresponding default axis
                                    axes = get_axes()
                                    axis_index = int(stepper) - 1
                                    settings[stepper_key][key] = axes[axis_index] if axis_index < len(axes) else default_value
                                else:
                                    settings[stepper_key][key] = default_value
                    
                    return settings
                    
        except (json.JSONDecodeError, IOError) as e:
            logger.error(f"Error reading settings file: {e}")
        
        return {}
