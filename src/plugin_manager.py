import asyncio
import importlib
from collections.abc import Sequence
from typing import Any

from utils import get_logger


class PluginManager:
    def __init__(self) -> None:
        self.plugins = []
        self.logger = get_logger()

    async def load_plugins(self) -> None:
        """Load all plugins."""
        plugin_names = ["bitwarden"]  # Remove "other_plugin" if it doesn't exist
        for module_name in plugin_names:
            try:
                module = importlib.import_module(f"plugins.{module_name}")
                plugin_class = getattr(module, f"{module_name.capitalize()}Plugin")
                plugin = plugin_class()
                self.plugins.append(plugin)
                self.logger.info("Loaded plugin: %s", module_name)
            except Exception as e:
                self.logger.exception("Error loading plugin %s: %s", module_name, str(e))

    def get_plugins(self) -> list:
        return self.plugins

    async def run_plugin_pipeline(self, method_name: str, *args: object, **kwargs: object) -> Sequence[object]:
        results = []
        for plugin in self.plugins:
            if hasattr(plugin, method_name):
                method = getattr(plugin, method_name)
                result = await method(*args, **kwargs)
                results.append(result)
        return results

    async def initialize_plugins(self) -> None:
        """Initialize all loaded plugins."""
        await asyncio.gather(*(plugin.initialize() for plugin in self.plugins))

    async def cleanup_plugins(self) -> None:
        """Cleanup all loaded plugins."""
        await asyncio.gather(*(plugin.cleanup() for plugin in self.plugins))

    async def on_navigation(self, url: str) -> None:
        """Handle navigation events."""
        await asyncio.gather(*(plugin.on_navigation(url) for plugin in self.plugins))

    async def on_element_detection(self, elements: dict[int, dict[str, Any]]) -> None:
        """Handle element detection events."""
        await asyncio.gather(*(plugin.on_element_detection(elements) for plugin in self.plugins))

    async def pre_action(self, action: dict[str, Any], elements: dict[int, dict[str, Any]]) -> dict[str, Any]:
        """Handle pre-action events."""
        for plugin in self.plugins:
            action = await plugin.pre_action(action, elements)
        return action

    async def post_action(self, action: dict[str, Any], success: bool) -> None:
        """Handle post-action events."""
        await asyncio.gather(*(plugin.post_action(action, success) for plugin in self.plugins))

    async def on_error(self, error: Exception) -> None:
        """Handle errors."""
        await asyncio.gather(*(plugin.on_error(error) for plugin in self.plugins))

    async def pre_decision(
        self, mapped_elements: dict[int, dict[str, Any]], current_url: str,
    ) -> tuple[bool, list[dict[str, Any]]]:
        for plugin in self.plugins:
            if hasattr(plugin, "pre_decision"):
                action_taken, actions = await plugin.pre_decision(mapped_elements, current_url)
                if action_taken:
                    return True, actions
        return False, None
