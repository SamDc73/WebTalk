from typing import Any

from analyzers.base_analyzer import BaseAnalyzer
from model_manager import ModelManager
from utils import get_logger


class DecisionMaker:
    def __init__(self, model_manager: ModelManager, analyzer: BaseAnalyzer, verbose: bool) -> None:
        self.logger = get_logger()
        self.model_manager = model_manager
        self.analyzer = analyzer
        self.verbose = verbose

    async def make_decision(
        self,
        mapped_elements: dict[int, dict[str, object]],
        task: str,
        current_url: str,
        plugin_data: dict[str, Any],
    ) -> str | None:
        context = {
            "mapped_elements": mapped_elements,
            "task": task,
            "current_url": current_url,
            "plugin_data": plugin_data,
        }
        decision = await self.analyzer.analyze(context)

        if self.verbose:
            self.logger.debug("AI Decision: %s", decision)
        return decision

    def parse_decision(self, decision: str) -> list[dict[str, object]]:
        if decision.upper() == "DONE":
            return []

        actions = []
        for action_str in decision.split(";"):
            action_str = action_str.strip()
            if ":" in action_str:
                element, text = action_str.split(":", 1)
                try:
                    element = int(element.strip())
                    actions.append({"type": "input", "element": element, "text": text.strip()})
                except ValueError:
                    self.logger.error(f"Invalid element number in input action: {action_str}")
            else:
                if action_str.upper() == "ENTER":
                    actions.append({"type": "submit"})
                elif action_str.lower().startswith("click on"):
                    try:
                        element = int(action_str.split()[-1])
                        actions.append({"type": "click", "element": element})
                    except ValueError:
                        self.logger.error(f"Invalid click instruction: {action_str}")
                else:
                    try:
                        element = int(action_str)
                        actions.append({"type": "click", "element": element})
                    except ValueError:
                        self.logger.error(f"Invalid action in decision: {action_str}")

        return actions

    async def is_task_completed(self, task: str, current_url: str) -> bool:
        return await self.analyzer.is_task_completed(task, current_url)
