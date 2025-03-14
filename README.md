## Scant-TUI

ScAnt Terminal User Interface

A simplified version of the scAnt GUI, for use on an Ubuntu-based system. Runs directly in the terminal. Tested on Ubuntu 20.04 LTS.

## Screenshot

![Screenshot](./docs/scAnt-tui-screenshot.png)

### Installation, Ubuntu

1. Install the dependencies:
```
sudo apt install python3 python3-pip
```
2. Install these packages into a new virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip3 install gphoto2 --only-binary :all:
pip3 install pyusb ticlib textual textual-dev textual[syntax] textual-slider Pillow imageio rawpy ticlib kafka-python[crc32c]
```
3. Install the Ubuntu drivers for Stepper motor controllers ([reference](https://www.pololu.com/product/3134/resources))
```bash
cd bin
tar -xf pololu-tic-1.8.1-linux-x86.tar.xz # Unzip the pololu-tic-1.8.1-linux-x86.tar.xz
cd pololu-tic-1.8.1-linux-x86 # The instructions, inside the README.txt are repeated here
sudo ./install.sh
cd ../..
ticcmd -h # Confirm that the installation worked
```
4. Install gphoto2 CLI ([reference](https://sourceforge.net/projects/gphoto/files/gphoto/2.5.28/gphoto2-2.5.28.tar.xz/download))
```bash
sudo apt install gphoto2
gphoto2 --auto-detect # Confirm that the installation worked
```
5. Add the current user to the group that can access the USB ports:
```bash
sudo adduser $USER dialout
sudo adduser $USER plugdev
```

### Configuration

#### WSL notes

In addition to the below *Configure devices* section, WSL users can try:

1. Install win-usbipd via Powershell Windows Package Manager, then run ([reference](https://github.com/dorssel/usbipd-win)):
```powershell
winget install usbipd
usbipd list # Confirm the USB devices are plugged in and visible on the Windows Host e.g 3-1    1ffb:00bd  Pololu Tic T500 Not Shared
usbipd bind --busid=<BUSID> # Do this for each Pololu Tic T500 USB devices and the Canon camera, may require administrator Powershell, until they are 'Shared'
usbipd attach --wsl --busid=<BUSID> # Do this for each Pololu Tic T500 and Canon camera
```

#### Configure devices

1. Plug-in the Pololu Tic500 stepper motors via USB or USB hub, and confirm they are detected by the system:
```bash
ticcmd --list
```
2. Plug-in the Canon camera via USB or USB hub, and confirm it is detected by the system:
```bash
gphoto2 --auto-detect
```

These should return information about the devices (names of stepper motors and Canon camera). To test these within the Python environment:

3. Confirm that Python, USB, camera, stepper motors are working:
```bash
python3 examples/test_gphoto2_camera_capture.py
python3 examples/test_gphoto2_camera_info.py
python3 examples/test_libtic.py
```

### Usage

Simply run:

```bash
python3 scripts/main.py
```

For development run:

```bash
textual console -x SYSTEM -x EVENT -x DEBUG -x INFO # textual console -v for verbose logs
textual run --dev scripts/main.py
```

### Notes

Current limit settings: https://www.pololu.com/docs/0J71/6#setting-current-limit
Maximum current limit for Tic T500 for the Pitch/ Yaw servo is 2131 mA.
Others are uncertain, believed to be 1000 mA.

Ranges for stepper motors:

Tilt: 10 positions, -15000 to 12000 with middle zeroing, speed 10000-50000
Yaw: 18 positions,0 to 1800 with no zeroing, speed 1000
Forward: 0 to 170000 with middle zeroing, speed 50000



