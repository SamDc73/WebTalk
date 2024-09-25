import litellm
import os
from dotenv import load_dotenv

# Disable debugging long messages
litellm._logging._disable_debugging()

class ModelManager:
    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model
        litellm.api_key = self.api_key

    @classmethod
    def initialize(cls, model_name="gpt-4"):
        load_dotenv()
        api_key = cls.check_api_key()
        return cls(api_key, model_name)

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

    async def parse_initial_message(self, message):
        try:
            response = await self.get_completion([
                {"role": "system", "content": "You are an AI assistant that extracts the website URL and task from a given message. Respond with only the URL and task, separated by a newline."},
                {"role": "user", "content": message}
            ])
            url, task = response.strip().split('\n')
            return url.strip(), task.strip()
        except Exception as e:
            print(f"Error parsing initial message: {e}")
            return None, None

    @staticmethod
    def check_api_key():
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("API key not found. Please check your .env file.")
            new_key = input("Enter your OpenAI API key: ")
            os.environ["OPENAI_API_KEY"] = new_key
            with open(".env", "a") as f:
                f.write(f"\nOPENAI_API_KEY={new_key}")
            print("API key has been saved to .env file.")
        return os.getenv("OPENAI_API_KEY")