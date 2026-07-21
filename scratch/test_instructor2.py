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
    
    try:
        resp = await client.chat.completions.create(
            model="openai/glm-5.2",
            response_model=Output,
            messages=[{"role": "user", "content": "Hola"}],
            api_key=api_key,
            api_base=base_url
        )
        print("Response:", resp.model_dump())
        if hasattr(resp, '_raw_response'):
            print("Usage:", resp._raw_response.usage)
        else:
            print("No _raw_response found")
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    asyncio.run(test())
