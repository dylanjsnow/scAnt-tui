#!/usr/bin/env python3
import asyncio
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from utils import serializer, deserializer

# sent_one = False

# async def send_one():
#     producer = AIOKafkaProducer(bootstrap_servers='kafka:29092', value_serializer=serializer)
#     # Get cluster layout and initial topic/partition leadership information
#     await producer.start()
#     try:
#         # Produce message
#         await producer.send_and_wait("scant.system.logs", {"response":"good"})
#     finally:
#         # Wait for all pending messages to be delivered or expire.
#         await producer.stop()
        
async def consume():
    consumer = AIOKafkaConsumer(
        'scant.control.commands',
        bootstrap_servers='kafka:29092',
        value_deserializer=deserializer)
    # Get cluster layout and join group `my-group`
    await consumer.start()
    try:
        # Consume messages
        print("camera.py: Consuming messages")
        async for msg in consumer:
            print("consumed: ", msg)
            # if not sent_one:
            #     await send_one()
            #     sent_one = True
    finally:
        # Will leave consumer group; perform autocommit if enabled.
        await consumer.stop()
        
        


asyncio.run(consume())