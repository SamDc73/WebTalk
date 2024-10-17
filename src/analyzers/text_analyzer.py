from typing import Any

from model_manager import ModelManager
from utils import extract_key_value_pairs, format_prompt, get_logger, load_prompt

from .base_analyzer import BaseAnalyzer


class TextAnalyzer(BaseAnalyzer):
    def __init__(self, model_manager: ModelManager) -> None:
        self.model_manager = model_manager
        self.logger = get_logger()
        self.prompt_template = load_prompt("text_analyzer")

    async def analyze(self, context: dict[str, Any]) -> str:
        prompt = self.generate_prompt(context)
        try:
            decision = await self.model_manager.get_completion(
                [
                    {"role": "system", "content": prompt["system_message"]},
                    {"role": "user", "content": prompt["user_message"]},
                ],
            )
            return decision
        except Exception as e:
            self.logger.exception("Error with AI model: %s", str(e))
            return None

    def generate_prompt(self, context: dict[str, Any]) -> dict[str, str]:
        mapped_elements = context["mapped_elements"]
        task = context["task"]
        current_url = context["current_url"]
        plugin_data = context["plugin_data"]

        elements_description = "\n".join(
            f"{num}: {info['description']} ({info['type']})" for num, info in mapped_elements.items()
        )

        task_info = extract_key_value_pairs(task)
        task_instructions = "\n".join(f"- Fill '{key}' with '{value}'" for key, value in task_info.items())

        plugin_info = "\n".join(f"- {key}: {value}" for key, value in plugin_data.items())

        return format_prompt(
            self.prompt_template,
            task=task,
            current_url=current_url,
            elements_description=elements_description,
            task_instructions=task_instructions,
            plugin_info=plugin_info,
        )

    async def is_task_completed(self, task: str, current_url: str) -> bool:
        prompt = f"""Task: {task}
Current URL: {current_url}

Is the task completed? Respond with 'Yes' if the task is completed, or 'No' if it's not."""

        try:
            completion = await self.model_manager.get_completion(
                [
                    {
                        "role": "system",
                        "content": "You are an AI assistant that determines if a web navigation task is completed.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            return completion.strip().lower() == "yes"
        except Exception as e:
            self.logger.exception("Error checking task completion: %s", str(e))
            return False
