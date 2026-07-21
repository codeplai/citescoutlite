import asyncio
import os
import instructor
from litellm import acompletion
from pydantic import BaseModel

class Output(BaseModel):
    mensaje: str

async def test():
    client = instructor.from_litellm(acompletion)
    api_key = os.getenv("HUAWEI_MAAS_API_KEY", "test")
    base_url = os.getenv("HUAWEI_MAAS_BASE_URL", "https://api-ap-southeast-1.modelarts-maas.com/openai/v1")
    
    # We will just print the dir of the client to see if create_with_completion exists
    print(dir(client.chat.completions))

asyncio.run(test())
