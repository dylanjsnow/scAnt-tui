#!/usr/bin/env python3
import logging
from typing import Optional, Set
import json
from websockets.asyncio.client import ClientConnection
from datetime import datetime
import websockets
import asyncio
from websockets.server import WebSocketServerProtocol

class ScantCommunication:
    """Client class for connecting to the UI server and sending messages."""
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger()
        self.websocket = None
        self.uri = "ws://scant-ui:8765"
        self._connected = False

    async def connect(self, message_handler):
        """
        Maintain a websocket connection to the UI server.
        
        Args:
            message_handler: Async function that handles received messages
        """
        while True:
            try:
                await self.send("websocket", f"Attempting to connect to {self.uri}", logging.INFO)
                
                async with websockets.connect(self.uri) as websocket:
                    self.websocket = websocket
                    self._connected = True
                    await self.send("websocket", "Connected to server", logging.INFO)
                    
                    while True:
                        try:
                            message = await websocket.recv()
                            await message_handler(message)
                        except websockets.exceptions.ConnectionClosed:
                            await self.send("websocket", "Connection closed, attempting to reconnect...", logging.WARN)
                            break
                            
            except Exception as e:
                await self.send("websocket", f"Error in websocket connection: {e}", logging.ERROR)
                
            self.websocket = None
            self._connected = False
            await self.send("websocket", "Waiting 5 seconds before reconnecting...", logging.INFO)
            await asyncio.sleep(5)

    async def send(self, topic: str, message: str, level: int = logging.INFO) -> None:
        """
        Asynchronously log a message and also send it via websocket.
        
        Args:
            topic: Topic path (e.g. 'camera.capture', 'camera.status')
            message: The message content to log and send
            level: Message severity level from logging module
        """
        formatted_message = {
            "topic": f"{topic}",  # Ensure scant prefix
            "message": message,
            "level": logging.getLevelName(level),
            "timestamp": datetime.now().isoformat(),
        }
        
        self.logger.log(level, f"{formatted_message['topic']}: {message}")
        
        if self.websocket and self._connected:
            try:
                await self.websocket.send(json.dumps(formatted_message))
            except Exception as e:
                self.logger.error(f"Failed to send message via websocket: {e}")

class ScantCommunicationServer:
    """Server class for handling websocket connections and broadcasting messages."""
    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger()
        self.connections: Set[WebSocketServerProtocol] = set()
        self.ui_message_handler = None
        self.server = None
        self._running = False

    async def handle_connect(self, websocket: WebSocketServerProtocol):
        """Register the new websocket connection, handle incoming messages and remove the connection when it is closed."""
        try:
            self.connections.add(websocket)
            if self.ui_message_handler:
                await self.ui_message_handler(self.connections)
            self.logger.info(f"New connection established from {websocket.remote_address}. Total connections: {len(self.connections)}")
            
            async for data in websocket:
                try:
                    if self.ui_message_handler and self._running:
                        await self.ui_message_handler(data)
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Connection closed normally by {websocket.remote_address}")
        except Exception as e:
            self.logger.error(f"Error handling websocket connection: {e}")
        finally:
            self.connections.remove(websocket)
            if self.ui_message_handler:
                await self.ui_message_handler(self.connections)
            self.logger.info(f"Connection closed. Remaining connections: {len(self.connections)}")

    async def start(self, message_handler=None):
        """Start the websocket server."""
        self.ui_message_handler = message_handler
        self._running = True
        self.logger.info("Starting websocket server on port 8765")
        self.server = await websockets.serve(self.handle_connect, "0.0.0.0", 8765)
        await self.server.wait_closed()

    async def stop(self):
        """Stop the websocket server."""
        if self.server:
            self._running = False
            self.server.close()
            await self.server.wait_closed()
            self.server = None
            self.logger.info("Websocket server stopped")

    def broadcast(self, message: str):
        """Broadcast a message to all connected clients."""
        if self._running:
            websockets.broadcast(self.connections, message)

