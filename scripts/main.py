from kafka import KafkaProducer
from nicegui import ui

ui.label("Hello, World!")
ui.button("Click me", on_click=lambda: ui.notify("Hello, World!"))

# A Kafka producer that produces messages to a Kafka topic when button is pressed
producer = KafkaProducer(bootstrap_servers="localhost:9092")
ui.button("Produce message", on_click=lambda: producer.send("test", "Hello, World from Kafka!"))

ui.run()
