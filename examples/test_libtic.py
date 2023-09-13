import subprocess

print("Print out all current TIC stepper motors connected via USB")
print(r'Run "ticcmd --list" to get a list of all connected Tic devices.')
motor_serial_numbers = subprocess.check_output(["ticcmd", "--list"]).decode("utf-8").splitlines()

print("Extract just the first number from each line e.g")
print("'00425332,         Tic T500 Stepper Motor Controller            ' returns '00425332'")
motor_serial_numbers = [line.split(",")[0] for line in motor_serial_numbers]

print("Serial numbers of all connected Tic devices: ", motor_serial_numbers)