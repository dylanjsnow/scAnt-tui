#!/usr/bin/env python3
import asyncio
import websockets
import logging
from communication import ScantCommunicationClient, logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

communication = ScantCommunicationClient(logger=logger)

async def connect_to_websocket():
    """Connect to the websocket server on scant-ui and handle messages."""
    uri = "ws://scant-ui:8765"
    
    while True:
        try:
            await communication.send("scant.motor.websocket", f"Attempting to connect to {uri}", logging.INFO)
            
            async with websockets.connect(uri) as websocket:
                await communication.send("scant.motor.websocket", "Connected to websocket server", logging.INFO)
                
                while True:
                    try:
                        message = await websocket.recv()
                        await communication.send("scant.motor.websocket", f"Received message: {message}", logging.INFO)
                        
                        await communication.send("scant.motor.capture", "Photo capture completed successfully", logging.INFO)
                            
                    except websockets.exceptions.ConnectionClosed:
                        await communication.send("scant.motor.websocket", "Connection closed, attempting to reconnect...", logging.WARN)
                        break
                        
        except Exception as e:
            await communication.send("scant.motor.websocket", f"Error in websocket connection: {e}", logging.ERROR)
            
        await communication.send("scant.motor.websocket", "Waiting 5 seconds before reconnecting...", logging.INFO)
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect_to_websocket())
