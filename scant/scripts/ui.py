#!/usr/bin/env python3
import asyncio
import json
import logging
from typing import Set
import websockets
from websockets.server import WebSocketServerProtocol
from nicegui import app, ui

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

CONNECTIONS: Set[WebSocketServerProtocol] = set()

ui.label('Websockets demo').classes('text-2xl')
ui.label('Run this in the console to connect:')
ui.code('python -m websockets ws://scant-ui:8765/').classes('pr-8 pt-1 h-12')
with ui.row().classes('items-center'):
    connections_label = ui.label('0')
    ui.label('connections')
    ui.button('send hello', on_click=lambda: websockets.broadcast(CONNECTIONS, 'Hello!')).props('flat')
ui.separator().classes('mt-6')
ui.label('Log:')
messages = ui.scroll_area().classes('w-350 h-350 ml-4 border messages-container')

async def handle_connect(websocket: WebSocketServerProtocol):
    """Register the new websocket connection, handle incoming messages and remove the connection when it is closed."""
    try:
        CONNECTIONS.add(websocket)
        connections_label.text = len(CONNECTIONS)
        logger.info(f"New connection established from {websocket.remote_address}. Total connections: {len(CONNECTIONS)}")
        
        async for data in websocket:
            try:
                # Parse the data if it's JSON
                try:
                    # Try to parse as JSON
                    parsed_data = json.loads(data)
                    message_text = f"Received: {parsed_data.get('topic', '')}: {parsed_data.get('message', '')}"
                except json.JSONDecodeError:
                    # If not JSON, use raw data
                    message_text = f"Received: {data}"
                
                # Use with_content instead of add for ScrollArea
                with messages:
                    ui.label(message_text).classes('break-all')
                
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Connection closed normally by {websocket.remote_address}")
    except Exception as e:
        logger.error(f"Error handling websocket connection: {e}")
    finally:
        CONNECTIONS.remove(websocket)
        connections_label.text = len(CONNECTIONS)
        logger.info(f"Connection closed. Remaining connections: {len(CONNECTIONS)}")


async def start_websocket_server():
    logger.info("Starting websocket server on port 8765")
    async with websockets.serve(handle_connect, "0.0.0.0", 8765):
        await asyncio.Future()

# start the websocket server when NiceGUI server starts
app.on_startup(start_websocket_server)

ui.run()