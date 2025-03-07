import subprocess   
from enum import Enum
def get_stepper_motor_serial_numbers():
    print("Print out all current TIC stepper motors connected via USB")
    print(r'Run "ticcmd --list" to get a list of all connected Tic devices.')
    print("Extract just the first number from each line e.g")
    print("'00425332,         Tic T500 Stepper Motor Controller            ' returns '00425332'")
    motor_serial_numbers = subprocess.check_output(["ticcmd", "--list"]).decode("utf-8").splitlines()
    motor_serial_numbers = [line.split(",")[0] for line in motor_serial_numbers]
    print("Serial numbers of all connected Tic devices: ", motor_serial_numbers)
    return motor_serial_numbers

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
    IDLE = "idle"
    MOVING = "moving" 
    WAITING = "waiting"