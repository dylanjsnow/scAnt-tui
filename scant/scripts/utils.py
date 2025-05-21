#!/usr/bin/env python3
import logging
from typing import Optional
import json
from websockets.asyncio.client import ClientConnection
from datetime import datetime
import websockets
import asyncio

class ScantCommunication:
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
                            await message_handler(message) # Logic for handling messages
                        except websockets.exceptions.ConnectionClosed:
                            await self.send("websocket", "Connection closed, attempting to reconnect...", logging.WARN)
                            break
                            
            except Exception as e:
                await self.send("websocket", f"Error in websocket connection: {e}", logging.ERROR)
                
            self.websocket = None
            self._connected = False
            await self.send("websocket", "Waiting 5 seconds before reconnecting...", logging.INFO)
            await asyncio.sleep(5)

    async def send(
        self,
        topic: str,
        message: str,
        level: int = logging.INFO,
    ) -> None:
        """
        Asynchronously log a message and also send it via websocket.
        
        Args:
            topic: Topic path (e.g. 'camera.capture', 'camera.status')
            message: The message content to log and send
            level: Message severity level from logging module
        """
        # Format the message with the topic
        formatted_message = {
            "topic": f"scant.{topic}",  # Ensure scant prefix
            "message": message,
            "level": logging.getLevelName(level),
            "timestamp": datetime.now().isoformat(),
        }
        
        # Log the message
        self.logger.log(level, f"{formatted_message['topic']}: {message}")
        
        # Send via websocket if available
        if self.websocket and self._connected:
            try:
                await self.websocket.send(json.dumps(formatted_message))
            except Exception as e:
                self.logger.error(f"Failed to send message via websocket: {e}")
