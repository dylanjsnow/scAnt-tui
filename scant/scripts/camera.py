#!/usr/bin/env python3
import asyncio
import websockets
import logging
import gphoto2 as gp
import os
from PIL import Image
from datetime import datetime
import subprocess
from enum import Enum
from utils import ScantCommunication, logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

communication = ScantCommunication(logger=logger)

class CameraStatus(Enum):
    IDLE = "IDLE"
    CAPTURING = "CAPTURING"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"

async def take_photo(websocket=None):
    """Take a photo with the camera and save it to the results directory."""
    try:
        await communication.send("scant.camera.capture", "Starting photo capture", logging.INFO)
        await communication.send("scant.camera.status", CameraStatus.CAPTURING.value, logging.INFO)
        await communication.send("scant.camera.capture", "Creating results directory", logging.DEBUG)
        
        os.makedirs("./results", exist_ok=True)
        
        await communication.send("scant.camera.capture", "Generating filename with timestamp", logging.DEBUG)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"{timestamp}.jpg"
        final_path = os.path.join("./results", final_filename)
        
        await communication.send("scant.camera.capture", "Getting connected cameras", logging.DEBUG)
        
        cameras = get_connected_cameras()
        await communication.send("scant.camera.capture", f"Connected Cameras: {cameras}", logging.INFO)
        
        await communication.send("scant.camera.capture", "Initializing camera", logging.DEBUG)
        
        camera = gp.Camera()
        camera.init()
        
        await communication.send("scant.camera.capture", "Capturing image with gphoto2...", logging.INFO)
        
        file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
        await communication.send("scant.camera.capture", f'Camera file path: {file_path.folder}/{file_path.name}', logging.DEBUG)
        
        await communication.send("scant.camera.capture", f'Saving image to: {final_path}', logging.INFO)
        
        camera_file = camera.file_get(
            file_path.folder, 
            file_path.name, 
            gp.GP_FILE_TYPE_NORMAL
        )
        camera_file.save(final_path)
        
        await communication.send("scant.camera.capture", "Cleaning up camera handler", logging.DEBUG)
        
        camera.exit()
        
        await communication.send("scant.camera.status", CameraStatus.COMPLETED.value, logging.INFO)
        await communication.send("scant.camera.status", CameraStatus.IDLE.value, logging.INFO)
                
    except Exception as e:
        await communication.send("scant.camera.status", CameraStatus.ERROR.value, logging.ERROR)
        await communication.send("scant.camera.capture", f"Error taking photo: {str(e)}", logging.ERROR)

def get_connected_cameras() -> list:
    """Get a list of connected cameras using gphoto2."""
    try:
        # Run gphoto2 command to list cameras
        result = subprocess.run(
            ["gphoto2", "--auto-detect"], 
            capture_output=True, 
            text=True, 
            check=True
        )
        logger.debug("Connected Cameras: ", result.stdout)
        
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
        communication.send("scant.camera.error", "Error detecting cameras", logging.ERROR)
        return []
    except Exception as e:
        communication.send("scant.camera.error", f"Error: {str(e)}", logging.ERROR)
        return []
        
def save_image_with_exif(img, filename):
    """Save an image with comprehensive EXIF metadata."""
    try:
        # Get existing EXIF data
        exif = img.getexif() if hasattr(img, 'getexif') else Image.Exif()
        
        # Default values instead of UI fields
        current_date = datetime.now().strftime("%Y:%m:%d %H:%M:%S")
        subject = "Unknown Subject"
        owner = "SCANT System"
        yaw_position = "0.0"
        tilt_position = "0.0"
        forward_position = "0.0"
        project_name = "Default Project"
        subject_id = "000"
        scale = "1:1"
        software = "SCANT Camera System"
        copyright_info = "All Rights Reserved"
        notes = "Automatically captured image"
        
        # Create image description with metadata
        image_description = (
            f"Date: {current_date}\n"
            f"Subject: {subject}\n"
            f"Artist: {owner}\n"
            f"Yaw: {yaw_position}\n"
            f"Tilt: {tilt_position}\n"
            f"Forward: {forward_position}\n"
            f"Project: {project_name}\n"
            f"Subject ID: {subject_id}\n"
            f"Scale: {scale}\n"
            f"Software: {software}\n"
            f"Copyright: {copyright_info}\n"
            f"Notes: {notes}"
        )
        
        # Add standard EXIF tags
        exif[0x010e] = image_description.encode('ascii', 'replace')  # ImageDescription
        exif[0x013b] = owner.encode('ascii', 'replace')  # Artist
        exif[0x8298] = copyright_info.encode('ascii', 'replace')  # Copyright
        exif[0x0131] = software.encode('ascii', 'replace')  # Software
        exif[0x0132] = current_date  # DateTime
        exif[0x9003] = current_date  # DateTimeOriginal
        exif[0x9004] = current_date  # DateTimeDigitized

        # First save with EXIF data
        img.save(filename, 'JPEG', exif=exif, quality=100)
        
        logger.debug("Image saved with EXIF data and displayed")
        return True
    
    except Exception as e:
        logger.error(f"Error saving image with EXIF data: {e}")
        return False

async def connect_to_websocket():
    """Connect to the websocket server on scant-ui and handle messages."""
    uri = "ws://scant-ui:8765"
    
    while True:
        try:
            await communication.send("scant.camera.websocket", f"Attempting to connect to {uri}", logging.INFO)
            
            async with websockets.connect(uri) as websocket:
                await communication.send("scant.camera.websocket", "Connected to websocket server", logging.INFO)
                await communication.send("scant.camera.websocket", "Waiting for photo capture command...", logging.INFO)
                await communication.send("scant.camera.status", CameraStatus.IDLE.value, logging.INFO)
                while True:
                    try:
                        message = await websocket.recv()
                        await communication.send("scant.camera.websocket", f"Received message: {message}", logging.INFO)
                        
                        await take_photo(websocket)
                        
                        await communication.send("scant.camera.capture", "Photo capture completed successfully", logging.INFO)
                            
                    except websockets.exceptions.ConnectionClosed:
                        await communication.send("scant.camera.websocket", "Connection closed, attempting to reconnect...", logging.WARN)
                        break
                        
        except Exception as e:
            await communication.send("scant.camera.websocket", f"Error in websocket connection: {e}", logging.ERROR)
            
        await communication.send("scant.camera.websocket", "Waiting 5 seconds before reconnecting...", logging.INFO)
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect_to_websocket())
