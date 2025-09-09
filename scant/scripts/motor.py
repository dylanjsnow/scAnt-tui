#!/usr/bin/env python3
import asyncio
from enum import Enum
import json
import subprocess
import logging
from communication import ScantCommunicationClient, logging
from utils import MotorStatus, MotorAxis

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

communication = ScantCommunicationClient(logger=logger)
    
class Motor:  
    def __init__(self, serial_number: str):
        self.serial_number = serial_number
        self.axis = MotorAxis.FORWARD
        self.current_position = 0
        self.target_position = 0
        self.scan_state = MotorStatus.IDLE
    
    async def move_motor(self, axis: MotorAxis, position: float):
        """Move the motor to a specific position."""
        await communication.send("motor.move", f"Moving motor {self.axis} to {position}", logging.INFO)
        
    async def energize_motor(self, energize: bool):
        """Energize the motor."""
        await communication.send("motor.energize", f"Energizing motor {self.axis}", logging.INFO)
        
    async def deenergize_motor(self):
        """Deenergize the motor."""
        await communication.send("motor.deenergize", f"Deenergizing motor {self.axis}", logging.INFO)
    
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
        


async def initialize():
    stepper_motor_serial_numbers = get_stepper_motor_serial_numbers()
    yaw_motor = Motor(stepper_motor_serial_numbers[0])
    tilt_motor = Motor(stepper_motor_serial_numbers[1])
    forward_motor = Motor(stepper_motor_serial_numbers[2])  
    
    return yaw_motor, tilt_motor, forward_motor

async def handle_message(message: str):
    """Handle messages received from the UI."""
    await communication.send("motor.websocket", f"Received message: {message}", logging.INFO)
    message_json = json.loads(message)
    logger.info(f"Received message: {message_json}")
    if message_json["topic"] == "server.broadcast" and message_json["message"] == "MOVE_MOTOR":
        # await take_photo()
        await communication.send("motor.capture", "Started moving motor", logging.INFO)

    if message_json["topic"] == "server.broadcast" and message_json["message"] == "INITIALIZE":
        await communication.send("motor.info", "Initializing motors", logging.INFO)
        yaw_motor, tilt_motor, forward_motor = await initialize()
        await communication.send("motor.info", "Motors initialized", logging.INFO)
        await communication.send("motor.initialized", {
            "yaw_motor": yaw_motor.serial_number,
            "tilt_motor": tilt_motor.serial_number,
            "forward_motor": forward_motor.serial_number
        })

if __name__ == "__main__":
    asyncio.run(communication.connect(handle_message))

