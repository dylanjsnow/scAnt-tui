#!/usr/bin/env python3
from utils import serializer, deserializer
from multiprocessing import Manager, Queue
from aiokafka import AIOKafkaProducer, AIOKafkaConsumer
from nicegui import app, ui


async def send_one():
    producer = AIOKafkaProducer(bootstrap_servers='kafka:29092', value_serializer=serializer)
    # Get cluster layout and initial topic/partition leadership information
    await producer.start()
    try:
        # Produce message
        await producer.send_and_wait("scant.control.commands", {"key":"value"})
    finally:
        # Wait for all pending messages to be delivered or expire.
        await producer.stop()
        
async def consume():
    consumer = AIOKafkaConsumer(
        'scant.system.logs', 'scant.sensor.camera',
        bootstrap_servers='kafka:29092',
        value_deserializer=deserializer)
    # Get cluster layout and join group `my-group`
    await consumer.start()
    try:
        # Consume messages
        async for msg in consumer:
            print("consumed: ", msg)
    finally:
        # Will leave consumer group; perform autocommit if enabled.
        await consumer.stop()
        
        

ui.button('compute', on_click=send_one)
app.on_startup(consume)
ui.run()