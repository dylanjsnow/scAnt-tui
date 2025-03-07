from pathlib import Path
import json
import os
import time
from queue import Queue
from threading import Thread
from utils import get_axes

class SettingsManager:
    """Manages saving and loading of stepper motor settings"""
    
    def __init__(self, settings_file="settings.json"):
        """Initialize settings manager."""
        self.settings_file = Path(__file__).parent / settings_file
        print(f"\nInitializing SettingsManager with file: {self.settings_file}")
        
        self.settings = {
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
        
        # Create save queue for background saving
        self.save_queue = Queue()
        
        # Start background save thread
        self.save_thread = Thread(target=self._background_save, daemon=True)
        self.save_thread.start()
        
        # Load existing settings if available
        self.load_settings()
        print("SettingsManager initialization complete")

    def _get_default_settings(self) -> dict:
        """Get default settings structure."""
        return self.settings.copy()

    def _load_settings(self) -> dict:
        """Load raw settings from file"""
        try:
            if self.settings_file.exists():
                print(f"Reading settings from {self.settings_file}")
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
            print(f"Error reading settings file: {e}")
        
        return {}

    def queue_save(self, stepper_id: str, setting_type: str, value: str):
        """Queue a settings save operation"""
        stepper_key = f"stepper_{stepper_id}"
        print(f"Queueing save for {stepper_key} {setting_type}: {value}")
        
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
            print(f"Saving {setting_type} as string: {settings_copy[stepper_key][setting_type]}")
        else:
            settings_copy[stepper_key][setting_type] = value
        
        # Update internal settings
        self.settings = settings_copy
        
        # Queue the save operation
        self.save_queue.put(settings_copy)
        
        print("Current settings state:")
        print(json.dumps(self.settings, indent=2))

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

    def _background_save(self):
        """Background thread for saving settings atomically"""
        last_save = {}  # Keep track of last saved state
        
        while True:
            try:
                # Wait for new settings to save
                settings = self.save_queue.get()
                
                # Convert all values to strings and check if different from last save
                settings_to_save = {}
                changed = False
                
                for section, values in settings.items():
                    settings_to_save[section] = {
                        k: str(v) if v is not None else "" 
                        for k, v in values.items()
                    }
                    
                    # Check if this section changed
                    if (section not in last_save or 
                        settings_to_save[section] != last_save[section]):
                        changed = True
                
                # Only save if settings actually changed
                if changed:
                    print(f"Saving settings to {self.settings_file}")
                    
                    # Create directory if it doesn't exist
                    self.settings_file.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Write to temporary file first
                    temp_file = self.settings_file.with_suffix('.tmp')
                    with open(temp_file, 'w') as f:
                        json.dump(settings_to_save, f, indent=4)
                        f.flush()
                        os.fsync(f.fileno())
                    
                    # Rename temp file to actual file (atomic operation)
                    temp_file.replace(self.settings_file)
                    
                    # Update last saved state
                    last_save = settings_to_save.copy()
                
            except Exception as e:
                print(f"Error saving settings: {e}")
            
            time.sleep(0.1)  # Prevent excessive saves

    def load_settings(self):
        """Load settings from file, create if doesn't exist."""
        try:
            print(f"Attempting to load settings from {self.settings_file}")
            if self.settings_file.exists():
                # Load and parse the settings file
                loaded_settings = self._load_settings()
                if loaded_settings:
                    print("Settings file loaded successfully")
                    
                    # Update existing settings with loaded values
                    for section in self.settings:
                        if section in loaded_settings:
                            # Convert all values to strings
                            loaded_values = {
                                k: str(v) if v is not None else ""
                                for k, v in loaded_settings[section].items()
                            }
                            self.settings[section].update(loaded_values)
                    print("Settings merged with defaults")
                    
                    # Print loaded settings for debugging
                    print("Current settings after loading:")
                    print(json.dumps(self.settings, indent=2))
            else:
                print("Settings file not found, creating with defaults")
                self.save_queue.put(self.settings)
                
        except Exception as e:
            print(f"Error loading settings: {e}")
            print("Using default settings")
