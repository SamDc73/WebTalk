from typing import Any

from model_manager import ModelManager
from utils import get_logger, load_prompt

from .base_analyzer import BaseAnalyzer


class VisionAnalyzer(BaseAnalyzer):
    def __init__(self, model_manager: ModelManager) -> None:
        self.model_manager = model_manager
        self.logger = get_logger()
        self.prompt_template = load_prompt("vision_analyzer")

    async def analyze(self, context: dict[str, Any]) -> str:
        # TODO: Implement vision analysis
        pass

    def generate_prompt(self, context: dict[str, Any]) -> dict[str, str]:
        # TODO: Implement prompt generation for vision analysis
        pass
