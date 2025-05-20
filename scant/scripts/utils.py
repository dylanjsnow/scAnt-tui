#!/usr/bin/env python3
import logging
from typing import Optional
import json
from websockets.asyncio.client import ClientConnection
from datetime import datetime

class ScantCommunication:
    def __init__(self, logger: Optional[logging.Logger] = None, websocket: Optional[ClientConnection] = None):
        self.logger = logger or logging.getLogger()
        self.websocket = websocket

    async def send(
        self,
        topic: str,
        message: str,
        level: int = logging.INFO,
    ) -> None:
        """
        Asynchronously log a message and also send it via websocket.
        
        Args:
            topic: Hierarchical topic path (e.g. 'scant.camera.capture', 'scant.camera.status')
            message: The message content to log and send (e.g 'Starting photo capture', 'CAPTURING')
            level: Message severity level from logging module (e.g. logging.INFO, logging.DEBUG)
        """
        # Format the message with the topic
        formatted_message = {
            "topic": topic,
            "message": message,
            "level": logging.getLevelName(level),
            "timestamp": datetime.now().isoformat(),
        }
        
        # Log the message
        self.logger.log(level, f"{topic}: {message}")
        
        # Send via websocket if available
        if self.websocket:
            try:
                await self.websocket.send(json.dumps(formatted_message))
            except Exception as e:
                self.logger.error(f"Failed to send message via websocket: {e}")
