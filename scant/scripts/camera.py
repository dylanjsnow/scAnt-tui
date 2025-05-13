#!/usr/bin/env python3
import asyncio
import websockets
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

async def connect_to_websocket():
    """Connect to the websocket server on scant-ui and handle messages."""
    uri = "ws://scant-ui:8765"
    
    while True:
        try:
            logger.info(f"Attempting to connect to {uri}")
            async with websockets.connect(uri) as websocket:
                logger.info("Connected to websocket server")
                
                # Main message handling loop
                while True:
                    try:
                        message = await websocket.recv()
                        logger.info(f"Received message: {message}")
                        
                        # Try to parse as JSON if possible
                        try:
                            parsed_message = json.loads(message)
                            logger.info(f"Parsed JSON: {parsed_message}")
                        except json.JSONDecodeError:
                            # Not JSON, just use the raw message
                            pass
                            
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning("Connection closed, attempting to reconnect...")
                        break
                        
        except Exception as e:
            logger.error(f"Error in websocket connection: {e}")
            
        # Wait before attempting to reconnect
        logger.info("Waiting 5 seconds before reconnecting...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(connect_to_websocket())
