#!/usr/bin/env python3
import asyncio
import json
import logging
from typing import Set
from communication import ScantCommunicationServer
from websockets.server import WebSocketServerProtocol
from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments
from utils import MotorAxis, CURRENT_LIMIT_OPTIONS, MOTOR_AXIS_SERIALS  

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

server = ScantCommunicationServer(logger=logger)

def set_motor_target_position(event: ValueChangeEventArguments, motor_axis: MotorAxis):
    motor = event.sender.label
    print(motor)
    print(event.value)
    print(motor_axis)
def set_motor_speed(event: ValueChangeEventArguments, motor_axis: MotorAxis):
    motor = event.sender.label
    print("set_motor_speed")
    print(motor)
    print(event.value)
    print(event.sender)
    print(motor_axis)
def set_motor_axis_serial(event: ValueChangeEventArguments, motor_axis: MotorAxis, motor_serial_number: str):
    motor = event.sender.label
    print("set_motor_axis_serial")
    print(motor)
    print(event.value)
    print(event.sender)
    print(motor_axis)
    print(motor_serial_number)
    
ui.label('Scant UI').classes('text-3xl')

ui.label('Connections').classes('text-2xl')
with ui.row().classes('items-center'):
    ui.label('Active connections: ')
    connections_label = ui.label('0')
    ui.button('INITIALIZE', on_click=lambda: server.broadcast('INITIALIZE')).props('flat')
ui.separator().classes('mt-6')

ui.label('Cameras').classes('text-2xl')
with ui.row().classes('items-center'):
    ui.label('Active cameras: ')
    cameras_label = ui.label('0')
ui.separator().classes('mt-6')

@ui.refreshable
def motors_ui(motor_axis_serials: dict):
    for motor_axis_serial in motor_axis_serials:
        with ui.grid(columns=7).classes('items-center'):
            ui.label(motor_axis_serial.name)
            ui.select(options=[motor_axis_serials[axis] for axis in motor_axis_serials], 
                value=motor_axis_serials[motor_axis_serial], 
                on_change=lambda e, m=motor_axis_serial: set_motor_axis_serial(e, m))
            ui.input('Target position', 
                on_change=lambda e, m=motor_axis_serial: set_motor_target_position(e, m), 
                validation={'Input must be a number': lambda value: value.isdigit()})
            ui.html('Speed')
            ui.select(options=[label for label, value in CURRENT_LIMIT_OPTIONS], 
                value=CURRENT_LIMIT_OPTIONS[0][0], 
                on_change=lambda e, m=motor_axis_serial: set_motor_speed(e, m))
            ui.button('energize motor', on_click=lambda: server.broadcast('ENERGIZE_MOTOR')).props('flat')
            ui.button('deenergize motor', on_click=lambda: server.broadcast('DEENERGIZE_MOTOR')).props('flat')

ui.label('Motors').classes('text-2xl')
motor_axis_serials = MOTOR_AXIS_SERIALS # Initialize the motor axis serials, will be changed later
motors_ui(motor_axis_serials)

ui.separator().classes('mt-6')

# Log
ui.label('Log:').classes('text-2xl')
messages = ui.scroll_area().classes('w-350 h-350 ml-4 border messages-container')

async def handle_ui_message(data):
    """Handle incoming messages and update the UI."""
    if isinstance(data, Set):
        # Update connections display
        connections_label.text = ', '.join(str(conn.remote_address) for conn in data)
        return

    try:
        # Parse the data if it's JSON
        try:
            parsed_data = json.loads(data)
            message_text = f"Received: {parsed_data.get('topic', '')}: {parsed_data.get('message', '')}"
        except json.JSONDecodeError:
            message_text = f"Received: {data}"
        
        with messages:
            ui.label(message_text).classes('break-all')
            
        if parsed_data.get('topic') == 'motor.set_serial_numbers':
            motor_serial_numbers = parsed_data.get('message')
            for motor_serial_number in motor_serial_numbers:
                motor_serial_number_label = ui.label(motor_serial_number)
                motor_serial_number_label.classes('break-all')
                
        if parsed_data.get('topic') == 'motor.initialized':
            motor_axis_serial_numbers = parsed_data.get('message')
            print("motor_axis_serial_numbers: ", motor_axis_serial_numbers)
            new_motor_axis_serials = {
                MotorAxis.FORWARD: motor_axis_serial_numbers['forward_motor'],
                MotorAxis.TILT: motor_axis_serial_numbers['tilt_motor'],
                MotorAxis.YAW: motor_axis_serial_numbers['yaw_motor'],
            }
            motors_ui.refresh(new_motor_axis_serials)
                
        if parsed_data.get('topic') == 'camera.initialized':
            cameras = parsed_data.get('message')
            cameras_label.text = ', '.join(str(camera) for camera in cameras.get('cameras', []))

    
    except Exception as e:
        logger.error(f"Error processing message: {e}")

# start the websocket server when NiceGUI server starts
async def start_server():
    try:
        await server.start(handle_ui_message)
    except Exception as e:
        logger.error(f"Error starting server: {e}")

# Handle server startup and shutdown
app.on_startup(lambda: asyncio.create_task(start_server()))
app.on_shutdown(server.stop)

ui.run()