from kafka import KafkaProducer
from nicegui import ui

ui.label("Hello, World!")
ui.button("Click me", on_click=lambda: ui.notify("Hello, World!"))

# Use the service name 'kafka' and the internal port 29092
producer = KafkaProducer(bootstrap_servers="kafka:29092")

# Send to one of our defined topics
ui.button("Produce message", on_click=lambda: producer.send("scant.system.logs", b"Hello, World from Kafka!"))

ui.run()
