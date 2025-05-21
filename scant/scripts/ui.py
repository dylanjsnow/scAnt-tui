#!/usr/bin/env python3
import asyncio
import json
import logging
from typing import Set
from utils import ScantCommunicationServer
from nicegui import app, ui

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

server = ScantCommunicationServer(logger=logger)

ui.label('Scant UI').classes('text-2xl')
with ui.row().classes('items-center'):
    ui.label('Active connections: ')
    connections_label = ui.label('0')
    ui.button('test connections', on_click=lambda: server.broadcast('test')).props('flat')
ui.separator().classes('mt-6')
ui.label('Log:')
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