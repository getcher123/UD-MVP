import sys
from pathlib import Path
sys.path.append('c:/UD-MVP/app-ms')
from fastapi.testclient import TestClient
from main import app
from services import chatgpt_structured, normalize, listings

captured={}
chatgpt_structured.extract_structured_objects=lambda text: {'objects': []}
normalize.normalize_agentql_payload=lambda payload, rules: ([], [])
listings.flatten_objects_to_listings=lambda objects, rules, request_id, source_file: []

client=TestClient(app)
resp=client.post('/process_file', data={'output':'json'}, files={'file':('note.txt', b'hello', 'text/plain')})
print(resp.status_code, resp.text)
