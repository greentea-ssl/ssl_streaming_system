#!/usr/bin/env python3
# zmq_websocket_bridge.py
import asyncio
import json
import zmq
import zmq.asyncio
from websockets.server import serve
import logging
from typing import Set, Dict, Any

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("zmq_websocket_bridge")

# Connected WebSocket clients
connected_clients: Set = set()

# ZeroMQ configuration
ZMQ_SUBSCRIBER_URI = "tcp://localhost:5555"  # Connect to the orchestrator
ZMQ_TOPICS = [b"event"]  # Subscribe to 'event' topic

async def zmq_listener(context):
    """Listen for ZeroMQ messages and broadcast to WebSocket clients"""
    socket = context.socket(zmq.SUB)
    
    # Subscribe to topics
    for topic in ZMQ_TOPICS:
        socket.setsockopt(zmq.SUBSCRIBE, topic)
    
    logger.info(f"Connecting to ZeroMQ publisher at {ZMQ_SUBSCRIBER_URI}")
    socket.connect(ZMQ_SUBSCRIBER_URI)
    
    logger.info("ZeroMQ listener started")
    
    try:
        while True:
            try:
                # Receive multipart message [topic, payload]
                topic, payload = await socket.recv_multipart()
                
                # Decode the JSON payload
                try:
                    json_str = payload.decode('utf-8')
                    data = json.loads(json_str)
                    
                    # Create message with topic and data
                    message = {
                        "topic": topic.decode('utf-8'),
                        "data": data
                    }
                    
                    # Broadcast to all connected WebSocket clients
                    if connected_clients:
                        websocket_message = json.dumps(message)
                        await asyncio.gather(
                            *[client.send(websocket_message) for client in connected_clients]
                        )
                        logger.debug(f"Broadcasted message to {len(connected_clients)} clients")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                except UnicodeDecodeError as e:
                    logger.error(f"Unicode decode error: {e}")
                    
            except zmq.ZMQError as e:
                logger.error(f"ZMQ error: {e}")
                await asyncio.sleep(1)  # Wait before retrying
                
    finally:
        socket.close()
        logger.info("ZMQ listener stopped")

async def websocket_handler(websocket):
    """Handle WebSocket client connections"""
    # Register new client
    connected_clients.add(websocket)
    client_ip = websocket.remote_address[0]
    logger.info(f"New client connected: {client_ip} (Total clients: {len(connected_clients)})")
    
    try:
        # Keep the connection alive until client disconnects
        async for message in websocket:
            # We could process client messages here if needed
            # For now, we're just using one-way communication from ZMQ to clients
            pass
    except Exception as e:
        logger.error(f"Error handling WebSocket client {client_ip}: {e}")
    finally:
        # Unregister client
        connected_clients.remove(websocket)
        logger.info(f"Client disconnected: {client_ip} (Total clients: {len(connected_clients)})")

async def main():
    """Main entry point"""
    # Create ZeroMQ context
    context = zmq.asyncio.Context()
    
    # Start ZeroMQ listener
    zmq_task = asyncio.create_task(zmq_listener(context))
    
    # Start WebSocket server
    ws_host = "0.0.0.0"  # Listen on all interfaces
    ws_port = 8765
    logger.info(f"Starting WebSocket server on {ws_host}:{ws_port}")
    
    async with serve(websocket_handler, ws_host, ws_port):
        try:
            # Run forever
            await asyncio.Future()
        except asyncio.CancelledError:
            logger.info("Server task was cancelled")
        finally:
            # Cancel ZMQ listener task
            zmq_task.cancel()
            try:
                await zmq_task
            except asyncio.CancelledError:
                pass
            # Clean up ZeroMQ context
            context.term()
            logger.info("Server shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")