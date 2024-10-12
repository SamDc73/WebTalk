from abc import ABC, abstractmethod
from typing import Any


class BasePlugin(ABC):
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def cleanup(self) -> None:
        pass

    @abstractmethod
    def on_navigation(self, url: str) -> None:
        pass

    @abstractmethod
    def on_element_detection(self, elements: dict[int, dict[str, Any]]) -> None:
        pass

    async def pre_action(self, action: dict, mapped_elements: dict) -> dict:
        pass

    @abstractmethod
    async def post_action(self, action: dict, success: bool):
        pass

    @abstractmethod
    async def on_error(self, error: Exception):
        pass
