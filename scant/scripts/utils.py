import json

def serializer(unserialized):
    return json.dumps(unserialized).encode('utf-8')

def deserializer(serialized):
    return json.loads(serialized.decode('utf-8'))