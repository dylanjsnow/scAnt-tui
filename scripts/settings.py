from pathlib import Path
import json
import os
import time
from queue import Queue
from threading import Thread
from utils import get_axes

class SettingsManager:
    """Manages saving and loading of stepper motor settings"""
    
    def __init__(self):
        self.settings_file = Path(__file__).parent / "settings.json"
        self.save_queue = Queue()
        print(f"Initializing SettingsManager with settings file: {self.settings_file}")
        self.settings = self._load_settings()
        
        # Start background save thread
        self.save_thread = Thread(target=self._background_save, daemon=True)
        self.save_thread.start()

    def _get_default_settings(self) -> dict:
        """Get default settings using stepper_1's configuration as template"""
        return {
            "stepper_1": {
                "divisions": "",
                "min_position": "",
                "max_position": "",
                "current_limit": "2",
                "axis": "Forward",  # Default to first axis
                "serial": "",  # Will be set by first available serial
                "max_speed": "1000"
            }
        }

    def _load_settings(self) -> dict:
        """Load settings from file or return defaults"""
        try:
            if self.settings_file.exists():
                print(f"Loading settings from {self.settings_file}")
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
                                    
                    print(f"Loaded settings: {json.dumps(settings, indent=2)}")
                    return settings
                    
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading settings: {e}")
        
        # If no valid settings file exists, create default settings
        print("Using default settings")
        defaults = self._get_default_settings()["stepper_1"]
        settings = {}
        
        # Create settings for each stepper using defaults
        for stepper in ["1", "2", "3"]:
            stepper_key = f"stepper_{stepper}"
            settings[stepper_key] = defaults.copy()
            # Set appropriate axis for each stepper
            axes = get_axes()
            axis_index = int(stepper) - 1
            if axis_index < len(axes):
                settings[stepper_key]["axis"] = axes[axis_index]
                
        return settings

    def queue_save(self, stepper_id: str, setting_type: str, value: str):
        """Queue a settings save operation"""
        stepper_key = f"stepper_{stepper_id}"
        print(f"Queueing save for {stepper_key} {setting_type}: {value}")
        
        # Create a deep copy of current settings
        settings_copy = json.loads(json.dumps(self.settings))
        
        # Update the specific setting
        if stepper_key not in settings_copy:
            # If stepper doesn't exist, create it with defaults from stepper_1
            settings_copy[stepper_key] = json.loads(json.dumps(
                settings_copy.get("stepper_1", self._get_default_settings()["stepper_1"])
            ))
        
        settings_copy[stepper_key][setting_type] = value
        
        # Update internal settings and queue the save
        self.settings = settings_copy
        self.save_queue.put(settings_copy)
        
        print("Current settings state:")
        print(json.dumps(self.settings, indent=2))

    def get_setting(self, stepper_id: str, setting_type: str) -> str:
        """Get a setting value"""
        stepper_key = f"stepper_{stepper_id}"
        
        # If the stepper or setting doesn't exist, get default from stepper_1
        if stepper_key not in self.settings or setting_type not in self.settings[stepper_key]:
            default_value = ""
            if "stepper_1" in self.settings and setting_type in self.settings["stepper_1"]:
                default_value = self.settings["stepper_1"][setting_type]
            elif setting_type == "axis":
                # Special handling for axis - use corresponding default axis
                axes = get_axes()
                axis_index = int(stepper_id) - 1
                default_value = axes[axis_index] if axis_index < len(axes) else axes[0]
            
            return default_value
            
        value = self.settings[stepper_key][setting_type]
        print(f"Getting setting for {stepper_key} {setting_type}: {value}")
        return value

    def _background_save(self):
        """Background thread for saving settings atomically"""
        while True:
            try:
                # Wait for new settings to save
                settings = self.save_queue.get()
                print(f"Saving settings to {self.settings_file}:")
                print(json.dumps(settings, indent=2))
                
                # Write to temporary file first
                temp_file = self.settings_file.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(settings, f, indent=4)
                    f.flush()
                    os.fsync(f.fileno())  # Ensure write is complete
                    
                # Rename temp file to actual file (atomic operation)
                temp_file.replace(self.settings_file)
                    
            except Exception as e:
                print(f"Error saving settings: {e}")
            
            time.sleep(0.1)  # Prevent excessive saves
