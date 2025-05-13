#!/usr/bin/env python3
import asyncio
import websockets
import logging
import gphoto2 as gp
import os
from PIL import Image
from datetime import datetime
import subprocess
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def take_photo():
    try:
        logger.info(f"Taking photo")
        
        logger.info("Creating results directory if it doesn't exist")
        os.makedirs("./results", exist_ok=True)
        logger.info("Created results directory if it didn't exist")
        
        logger.info("Generating filename with timestamp")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        final_filename = f"{timestamp}.jpg"
        final_path = os.path.join("./results", final_filename)
        logger.info(f"Generated filename: {final_filename}")
        
        logger.info("Getting connected cameras")
        cameras = get_connected_cameras()
        logger.info(f"Connected Cameras: {cameras}")
        
        logger.info("Initializing camera")
        camera = gp.Camera()
        camera.init()
        logger.info("Camera initialized")
        
        logger.info("Capturing image with gphoto2...")
        file_path = camera.capture(gp.GP_CAPTURE_IMAGE)
        logger.info(f'Camera file path: {file_path.folder}/{file_path.name}')
        
        logger.info(f'Saving image to: {final_path}')
        camera_file = camera.file_get(
            file_path.folder, 
            file_path.name, 
            gp.GP_FILE_TYPE_NORMAL
        )
        camera_file.save(final_path)
        logger.info("Adding EXIF data to the saved image")
        # with Image.open(final_path) as img:
        #     if not save_image_with_exif(img, final_path):
        #         logger.error("Failed to apply EXIF data to image")
        #     else:
        #         logger.info("EXIF data successfully applied to image")
        # logger.info("Image saved from camera to final destination")
        
        logger.info("Cleaning up camera handler")
        camera.exit()
        logger.info("Camera connection closed")
        
        logger.info(f"Photo saved to: {final_path}")
                
    except Exception as e:
        logger.error(f"Error taking photo: {str(e)}")
        
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
        logger.error("Error detecting cameras")
        return []
    except Exception as e:
        logger.error(f"Error: {str(e)}")
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
            logger.info(f"Attempting to connect to {uri}")
            async with websockets.connect(uri) as websocket:
                logger.info("Connected to websocket server")
                
                # Main message handling loop
                while True:
                    try:
                        message = await websocket.recv()
                        logger.info(f"Received message: {message}")
                        
                        await take_photo()
                        
                        # Send a response back
                        response = "Responding with success"
                        logger.info(f"Sending response: {response}")
                        await websocket.send(response)
                        logger.info(f"Sent response: {response}")
                            
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Connection closed, attempting to reconnect...")
                        break
                        
        except Exception as e:
            logger.error(f"Error in websocket connection: {e}")
            
        # Wait before attempting to reconnect
        logger.info("Waiting 5 seconds before reconnecting...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect_to_websocket())
