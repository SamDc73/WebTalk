from abc import ABC, abstractmethod
from typing import Any


class BaseAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, context: dict[str, Any]) -> str:
        pass

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
