from kafka import KafkaConsumer, KafkaProducer
from datetime import datetime
import time
import json

class CameraWorker:
    def __init__(self):
        self.consumer = KafkaConsumer('scant.control.commands', bootstrap_servers='kafka:29092')
        self.producer = KafkaProducer(
            bootstrap_servers='kafka:29092',
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

    def start(self):
        print("Camera worker started...")
        
        for message in self.consumer:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"timestamp_{timestamp}.txt"
            
            self.producer.send('scant.system.logs', {
                'message': 'Saving image started',
                'timestamp': timestamp
            })
            
            self.producer.send('scant.sensor.camera', {
                'status': 'started',
                'timestamp': timestamp,
                'filename': filename
            })
            
            with open(filename, 'w') as f:
                try:
                    f.write(timestamp)
                except Exception as e:
                    error_msg = f"Error writing to file: {str(e)}"
                    self.producer.send('scant.system.logs', {
                        'message': error_msg,
                        'timestamp': timestamp,
                        'level': 'ERROR'
                    })
                    self.producer.send('scant.sensor.camera', {
                        'status': 'error',
                        'timestamp': timestamp,
                        'filename': filename,
                        'error': error_msg
                    })
                
            time.sleep(1)
            
            self.producer.send('scant.system.logs', {
                'message': f'Saving image complete: {filename}',
                'timestamp': timestamp
            })
            
            self.producer.send('scant.sensor.camera', {
                'status': 'completed',
                'timestamp': timestamp,
                'filename': filename
            })


