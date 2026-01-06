import os
from litellm import completion 
from pydantic import BaseModel
from src.models_litellm import *


messages = [
    {
        "role": "system", 
        "content": "You are a helpful assistant. **Always respond with a valid JSON object.**"
    },
    {"role": "user", "content": "Extract the user's name and age from 'John Doe is 30.'"}
]

class CalendarEvent(BaseModel):
  name: str
  date: str
  participants: list[str]

class EventsList(BaseModel):
    events: list[CalendarEvent]

os.environ['LM_STUDIO_API_KEY'] = ""
resp = completion(
    model="ollama/qwen3-vl:30b-a3b-instruct-bf16",
    messages=messages,
    response_format=EventsList
)

print("Received={}".format(resp.choices[0].message.content))