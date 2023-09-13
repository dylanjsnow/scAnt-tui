## Scant-TUI

ScAnt Terminal User Interface

A simplified version of the scAnt GUI, for use on an Ubuntu-based system. Runs directly in the terminal.

### Installation

1. Install the dependencies:
```
sudo apt install python3 python3-pip python3-tk python3-pil.imagetk
```
2. Install these packages into a new virtual environment:
```bash
python3 -m venv venv
source venv/bin/activate
pip3 install gphoto2 --only-binary :all:
pip3 install pyusb ticlib
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
# List all the USB devices and their owners
ls -l /dev/bus/usb/001


### Configuration

1. Plug-in the Pololu Tic500 stepper motors via USB or USB hub, and confirm they are detected by the system:
```bash
ticcmd --list
```
2. Plug-in the Canon camera via USB or USB hub, and confirm it is detected by the system:
```bash
gphoto2 --auto-detect
```

These should return information about the devices (names of stepper motors and Canon camera). 

### Usage

Take a photo and activate the stepper motors to check they are working within Python:
```bash
sudo python3 # Sudo needed to interface with the drivers

```# scAnt-tui
