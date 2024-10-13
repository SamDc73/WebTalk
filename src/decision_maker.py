import re

from model_manager import ModelManager
from utils import get_logger


class DecisionMaker:
    def __init__(self, model_manager: ModelManager, verbose: bool) -> None:
        self.logger = get_logger()
        self.model_manager = model_manager
        self.verbose = verbose

    def extract_key_value_pairs(self, task: str) -> dict[str, str]:
        pattern = r"(\w+(?:\s+\w+)*)\s+(?:is|it's|are)\s+['\"]?([\w@.]+)['\"]?"
        return dict(re.findall(pattern, task, re.IGNORECASE))

    async def make_decision(
        self,
        mapped_elements: dict[int, dict[str, object]],
        task: str,
        current_url: str,
    ) -> str | None:
        elements_description = "\n".join(
            f"{num}: {info['description']} ({info['type']})" for num, info in mapped_elements.items()
        )

        task_info = self.extract_key_value_pairs(task)
        task_instructions = "\n".join(f"- Fill '{key}' with '{value}'" for key, value in task_info.items())

        prompt = f"""Task: {task}
Current URL: {current_url}
Page elements:
{elements_description}

Information to use:
{task_instructions}

Decide the next action(s):
- To click an element, respond with the element number.
- To input text, respond with the element number followed by a colon and the text to input.
- To press Enter or submit a form, respond with "ENTER".
- For form filling, provide all necessary inputs in one decision, separated by semicolons (;), including the final submit action.
- For search tasks, input the search term and then click the search button.
- If the task is complete, respond with "DONE".

Your decision:"""

        try:
            decision = await self.model_manager.get_completion(
                [
                    {
                        "role": "system",
                        "content": "You are an AI assistant that navigates web pages. "
                        "Be decisive and provide all necessary actions to complete the task. "
                        "Use the exact information provided in the task for any inputs or actions. "
                        "Do not invent or assume any information not explicitly provided.",
                    },
                    {"role": "user", "content": prompt},
                ],
            )
            if self.verbose:
                self.logger.debug("AI Decision: %s", decision)
            return decision
        except Exception as e:
            self.logger.exception("Error with AI model: %s", str(e))
            return None

    def parse_decision(self, decision: str) -> list[dict[str, object]]:
        if decision.upper() == "DONE":
            return []

        actions = []
        for action_str in decision.split(";"):
            action_str = action_str.strip()
            if ":" in action_str:
                element, text = action_str.split(":", 1)
                element = int(element.strip())
                text = text.strip()
                actions.append({"type": "input", "element": element, "text": text})
            else:
                try:
                    element = int(action_str)
                    actions.append({"type": "click", "element": element})
                except ValueError:
                    self.logger.exception("Invalid action in decision: %s", action_str)

        return actions

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
