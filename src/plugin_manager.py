import importlib
from typing import Any

from utils import get_logger


class PluginManager:
    def __init__(self) -> None:
        self.plugins = []
        self.logger = get_logger()

    def load_plugins(self) -> None:
        """Load all plugins."""
        plugin_names = ["bitwarden", "other_plugin"]  # Add your plugin names here
        for module_name in plugin_names:
            try:
                module = importlib.import_module(f"plugins.{module_name}")
                plugin_class = getattr(module, f"{module_name.capitalize()}Plugin")
                plugin = plugin_class()
                self.plugins.append(plugin)
                self.logger.info("Loaded plugin: %s", module_name)
            except Exception as e:
                self.logger.exception("Error loading plugin %s: %s", module_name, str(e))

    def get_plugins(self):
        return self.plugins

    async def run_plugin_pipeline(self, method_name: str, *args, **kwargs):
        results = []
        for plugin in self.plugins:
            if hasattr(plugin, method_name):
                method = getattr(plugin, method_name)
                result = await method(*args, **kwargs)
                results.append(result)
        return results

    def initialize_plugins(self) -> None:
        """Initialize all loaded plugins."""
        for plugin in self.plugins:
            plugin.initialize()

    def cleanup_plugins(self) -> None:
        """Cleanup all loaded plugins."""
        for plugin in self.plugins:
            plugin.cleanup()

    def on_navigation(self, url: str) -> None:
        """Handle navigation events."""
        for plugin in self.plugins:
            plugin.on_navigation(url)

    def on_element_detection(self, elements: dict[int, dict[str, Any]]) -> None:
        """Handle element detection events."""
        for plugin in self.plugins:
            plugin.on_element_detection(elements)

    def pre_action(self, action: dict[str, Any], elements: dict[int, dict[str, Any]]) -> dict[str, Any]:
        """
        Handle pre-action events.

        Parameters
        ----------
        action : dict
            The action to be performed.
        elements : dict
            The detected elements.

        Returns
        -------
        dict
            The modified action.
        """
        for plugin in self.plugins:
            if "login" in action or "password" in action:
                self.logger.info("Delegating to Bitwarden for action: %s", action)
                action = plugin.pre_action(action, elements)
        return action

    def post_action(self, action: dict[str, Any], success: bool) -> None:
        """Handle post-action events."""
        for plugin in self.plugins:
            plugin.post_action(action, success)

    def on_error(self, error: Exception) -> None:
        """Handle errors."""
        for plugin in self.plugins:
            plugin.on_error(error)

    def pre_decision(self, mapped_elements: dict[int, dict[str, Any]], current_url: str) -> tuple[bool, str | None]:
        """
        Handle pre-decision events.

        Parameters
        ----------
        mapped_elements : dict
            The mapped elements.
        current_url : str
            The current URL.

        Returns
        -------
        tuple
            A tuple indicating whether an action was taken and the action.
        """
        for plugin in self.plugins:
            if hasattr(plugin, "pre_decision"):
                action_taken, action = plugin.pre_decision(mapped_elements, current_url)
                if action_taken:
                    return True, action
        return False, None
