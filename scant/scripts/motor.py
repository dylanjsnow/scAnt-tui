#!/usr/bin/env python3
import asyncio
import websockets
import logging
import gphoto2 as gp
import os
from PIL import Image
from datetime import datetime
import subprocess
from utils import ScantCommunication, MessageLevel
import json
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

communication = ScantCommunication(logger=logger)

async def take_photo(websocket=None):
    """Take a photo with the camera and save it to the results directory."""
    try:
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message="Starting photo capture",
            level=MessageLevel.INFO,

        )
        
        await communication.async_log_and_send(
            topic="scant.camera.status",
            message="CAPTURING",
            level=MessageLevel.INFO,

        )

        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message="Creating results directory",
            level=MessageLevel.DEBUG,

        )
        
        os.makedirs("./results", exist_ok=True)
        
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message="Generating filename with timestamp",
            level=MessageLevel.DEBUG,

        )
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"{timestamp}.jpg"
        final_path = os.path.join("./results", final_filename)
        
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message="Getting connected cameras",
            level=MessageLevel.DEBUG,

        )
        
        cameras = get_connected_cameras()
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message=f"Connected Cameras: {cameras}",
            level=MessageLevel.INFO,

        )
        
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message="Initializing camera",
            level=MessageLevel.DEBUG,

        )
        
        camera = gp.Camera()
        camera.init()
        
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message="Capturing image with gphoto2...",
            level=MessageLevel.INFO,

        )
        
        file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message=f'Camera file path: {file_path.folder}/{file_path.name}',
            level=MessageLevel.DEBUG,

        )
        
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message=f'Saving image to: {final_path}',
            level=MessageLevel.INFO,

        )
        
        camera_file = camera.file_get(
            file_path.folder, 
            file_path.name, 
            gp.GP_FILE_TYPE_NORMAL
        )
        camera_file.save(final_path)
        
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message="Cleaning up camera handler",
            level=MessageLevel.DEBUG,

        )
        
        camera.exit()
        
        await communication.async_log_and_send(
            topic="scant.camera.status",
            message="COMPLETED",
            level=MessageLevel.INFO,

        )
        
        await communication.async_log_and_send(
            topic="scant.camera.status",
            message="IDLE",
            level=MessageLevel.INFO,

        )
                
    except Exception as e:
        await communication.async_log_and_send(
            topic="scant.camera.capture",
            message=f"Error taking photo: {str(e)}",
            level=MessageLevel.ERROR,

        )

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
        log_and_send("scant.camera.error", "Error detecting cameras", logger)
        return []
    except Exception as e:
        log_and_send("scant.camera.error", f"Error: {str(e)}", logger)
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
            await communication.async_log_and_send(
                topic="scant.camera.websocket",
                message=f"Attempting to connect to {uri}",
                level=MessageLevel.INFO,
                logger=logger,
                websocket=None
            )
            
            async with websockets.connect(uri) as websocket:
                await communication.async_log_and_send(
                    topic="scant.camera.websocket",
                    message="Connected to websocket server",
                    level=MessageLevel.INFO,
                    logger=logger,
                    websocket=websocket
                )
                
                while True:
                    try:
                        message = await websocket.recv()
                        await communication.async_log_and_send(
                            topic="scant.camera.websocket",
                            message=f"Received message: {message}",
                            level=MessageLevel.INFO,
                            logger=logger,
                            websocket=websocket
                        )
                        
                        await take_photo(websocket)
                        
                        await communication.async_log_and_send(
                            topic="scant.camera.websocket",
                            message="Photo capture completed successfully",
                            level=MessageLevel.INFO,
                            logger=logger,
                            websocket=websocket
                        )
                            
                    except websockets.exceptions.ConnectionClosed:
                        await communication.async_log_and_send(
                            topic="scant.camera.websocket",
                            message="Connection closed, attempting to reconnect...",
                            level="WARN",
                            logger=logger,
                            websocket=None
                        )
                        break
                        
        except Exception as e:
            await communication.async_log_and_send(
                topic="scant.camera.websocket",
                message=f"Error in websocket connection: {e}",
                level=MessageLevel.ERROR,
                logger=logger,
                websocket=None
            )
            
        await communication.async_log_and_send(
            topic="scant.camera.websocket",
            message="Waiting 5 seconds before reconnecting...",
            level=MessageLevel.INFO,
            logger=logger,
            websocket=None
        )
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect_to_websocket())
