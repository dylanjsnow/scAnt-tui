import subprocess   
from enum import Enum, auto
import logging

# Create logger for this module
logger = logging.getLogger(__name__)

def get_stepper_motor_serial_numbers():
    logger.info("Getting list of connected TIC stepper motors")
    logger.debug("Running 'ticcmd --list' to get connected Tic devices")
    
    try:
        motor_serial_numbers = subprocess.check_output(["ticcmd", "--list"]).decode("utf-8").splitlines()
        motor_serial_numbers = [line.split(",")[0] for line in motor_serial_numbers]
        logger.info(f"Found {len(motor_serial_numbers)} connected Tic devices: {motor_serial_numbers}")
        return motor_serial_numbers
    except Exception as e:
        logger.error(f"Error getting stepper motor serial numbers: {e}")
        return []

def get_axes():
    return ["Forward", "Tilt", "Yaw"] # A.k.a Forward, Pitch, Heading (planes) or Z direction, X, Y (camera calibration computer vision)

def get_buttons_to_initialize():
    """Return a list of buttons that should be disabled until the stepper motor is initialized"""
    return ["run_stepper"]

def get_inputs_to_initialize():
    """Return a list of inputs that should be disabled until the stepper motor is initialized"""
    return ["divisions_stepper", "max_position_stepper", "min_position_stepper", "max_speed_stepper"]

class ScanState(Enum):
    """States for the scanning process"""
    IDLE = auto()
    MOVING = auto()
    WAITING = auto()

class CameraState(Enum):
    IDLE = auto()
    CAPTURING = auto()
    WAITING = auto()

class CameraMessage:
    """Message types for camera queue"""
    TAKE_PHOTO = "TAKE_PHOTO"
    PHOTO_COMPLETE = "PHOTO_COMPLETE"
    PHOTO_ERROR = "PHOTO_ERROR"