import litellm

class ModelManager:
    def __init__(self, api_key, model):
        litellm.api_key = api_key
        self.model = model

    async def get_completion(self, messages):
        try:
            response = await litellm.acompletion(
                model=self.model,
                messages=messages
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"Error getting completion from litellm: {e}")
            return None