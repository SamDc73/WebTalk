from abc import ABC, abstractmethod
from typing import Any


class PluginInterface(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the plugin."""

    @abstractmethod
    async def cleanup(self) -> None:
        """Clean up plugin resources."""

    @abstractmethod
    async def handle_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Handle an event."""

    @abstractmethod
    async def pre_decision(self, context: dict[str, Any]) -> dict[str, Any]:
        """Perform actions before a decision is made."""
        return {}

    @abstractmethod
    async def post_decision(self, decision: dict[str, Any], context: dict[str, Any]) -> None:
        """Perform actions after a decision is made."""
