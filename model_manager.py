from openai import AsyncOpenAI

class ModelManager:
    def __init__(self, api_key, model):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model

    async def get_completion(self, messages):
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error getting completion from OpenAI: {e}")
            return None