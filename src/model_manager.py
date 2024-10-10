import os
from collections.abc import Mapping, Sequence

import litellm
from dotenv import load_dotenv
from utils import get_logger


# Disable debugging long messages
litellm._logging._disable_debugging()


class ModelManager:
    def __init__(self, api_key: str, model: str) -> None:
        self.logger = get_logger()
        self.api_key = api_key
        self.model = model
        litellm.api_key = self.api_key

        # Set up Langfuse
        self.setup_langfuse()

    @classmethod
    def initialize(cls, model_provider: str = "openai") -> "ModelManager":
        load_dotenv()
        api_key = cls.check_api_key(model_provider)
        model = "gpt-4" if model_provider == "openai" else "groq/llama3-8b-8192"
        return cls(api_key, model)

    def setup_langfuse(self) -> None:
        langfuse_public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
        langfuse_secret_key = os.getenv("LANGFUSE_SECRET_KEY")
        langfuse_host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if langfuse_public_key and langfuse_secret_key:
            os.environ["LANGFUSE_PUBLIC_KEY"] = langfuse_public_key
            os.environ["LANGFUSE_SECRET_KEY"] = langfuse_secret_key
            os.environ["LANGFUSE_HOST"] = langfuse_host

            litellm.success_callback = ["langfuse"]
            litellm.failure_callback = ["langfuse"]
            self.logger.info("Langfuse integration enabled")
        else:
            self.logger.warning(
                "Langfuse integration not enabled. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env to enable."
            )

    async def get_completion(self, messages: Sequence[dict], **kwargs: Mapping) -> str | None:
        try:
            response = await litellm.acompletion(model=self.model, messages=messages, **kwargs)
            return response.choices[0].message.content.strip()
        except Exception as e:
            self.logger.error(f"Error getting completion from litellm: {e}")
            return None

    async def parse_initial_message(self, message: str) -> tuple[str | None, str | None]:
        try:
            response = await self.get_completion(
                [
                    {
                        "role": "system",
                        "content": (
                            "You are an AI assistant that extracts the website URL and task from a given message. "
                            "Respond with only the URL and task, separated by a newline."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                metadata={
                    "generation_name": "parse_initial_message",
                    "trace_id": "initial_parse",
                    "tags": ["initial_parsing"],
                },
            )
            url, task = response.strip().split("\n")
            return url.strip(), task.strip()
        except Exception as e:
            self.logger.error(f"Error parsing initial message: {e}")
            return None, None

    @staticmethod
    def check_api_key(model_provider: str) -> str:
        logger = get_logger()
        env_var = "OPENAI_API_KEY" if model_provider == "openai" else "GROQ_API_KEY"
        api_key = os.getenv(env_var)
        if not api_key:
            logger.warning(f"{model_provider.capitalize()} API key not found. Please check your .env file.")
            new_key = input(f"Enter your {model_provider.capitalize()} API key: ")
            os.environ[env_var] = new_key
            with open(".env", "a") as f:
                f.write(f"\n{env_var}={new_key}")
            logger.info(f"{model_provider.capitalize()} API key has been saved to .env file.")
        return os.getenv(env_var)
