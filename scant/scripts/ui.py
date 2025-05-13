#!/usr/bin/env python3
import asyncio
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
ui.label('Websocket messages:')
messages = ui.column().classes('ml-4')


async def handle_connect(websocket: WebSocketServerProtocol):
    """Register the new websocket connection, handle incoming messages and remove the connection when it is closed."""
    try:
        CONNECTIONS.add(websocket)
        connections_label.text = len(CONNECTIONS)
        logger.info(f"New connection established. Total connections: {len(CONNECTIONS)}")
        
        async for data in websocket:
            logger.info(f"Received message: {data}")
            with messages:
                ui.label(str(data))
            
            # Send acknowledgment back
            # await websocket.send(f"Received: {data}")
            # logger.info(f"Sent acknowledgment for message: {data}")
            
    except Exception as e:
        logger.error(f"Error handling websocket connection: {e}")
    finally:
        CONNECTIONS.remove(websocket)
        connections_label.text = len(CONNECTIONS)
        logger.info(f"Connection closed. Remaining connections: {len(CONNECTIONS)}")


async def start_websocket_server():
    logger.info("Starting websocket server on port 8765")
    async with websockets.serve(handle_connect, None, 8765):
        await asyncio.Future()

# start the websocket server when NiceGUI server starts
app.on_startup(start_websocket_server)

ui.run()