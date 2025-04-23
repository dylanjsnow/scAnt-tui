from datetime import datetime
import json
from kafka import KafkaProducer
from nicegui import ui
from init import init
import multiprocessing
from camera import CameraWorker

init()

# Start camera worker
camera_worker = CameraWorker()
camera_process = multiprocessing.Process(target=camera_worker.start)
camera_process.start()

ui.label("Hello, World!")
ui.button("Click me", on_click=lambda: ui.notify("Hello, World!"))

# Use the service name 'kafka' and the internal port 29092
producer = KafkaProducer(bootstrap_servers="kafka:29092")

# Send to one of our defined topics
ui.button("Trigger Camera", on_click=lambda: producer.send("scant.control.commands", json.dumps({"action": "capture", "timestamp": datetime.now().isoformat()}).encode('utf-8')))

ui.run()
