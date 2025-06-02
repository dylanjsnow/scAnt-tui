#!/usr/bin/env python3
import asyncio
import json
import logging
from typing import Set
from communication import ScantCommunicationServer
from websockets.server import WebSocketServerProtocol
from nicegui import app, ui
from nicegui.events import ValueChangeEventArguments
from utils import MotorAxis, CURRENT_LIMIT_OPTIONS

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
    print(motor)
    print(event.value)
    print(event.sender)
    print(motor_axis)

ui.label('Scant UI').classes('text-3xl')

ui.label('Connections').classes('text-2xl')
with ui.row().classes('items-center'):
    ui.label('Active connections: ')
    connections_label = ui.label('0')
    ui.button('test connections', on_click=lambda: server.broadcast('TEST')).props('flat')
ui.separator().classes('mt-6')

ui.label('Motors').classes('text-2xl')
for motor in MotorAxis:
    with ui.row().classes('items-center'):
        ui.label(motor)
        ui.input('Target position', 
            on_change=lambda e, m=motor: set_motor_target_position(e, m), 
            value="",
            validation={'Input must be a number': lambda value: value.isdigit()})
        ui.html('Speed')
        ui.select(options=[label for label, value in CURRENT_LIMIT_OPTIONS], 
            value=CURRENT_LIMIT_OPTIONS[0][0], 
            on_change=lambda e, m=motor: set_motor_speed(e, m))
ui.button('move motor', on_click=lambda: server.broadcast('MOVE_MOTOR')).props('flat')
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