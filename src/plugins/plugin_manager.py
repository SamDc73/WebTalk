import asyncio
import importlib
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

from utils import get_logger


if TYPE_CHECKING:
    from plugins.plugin_interface import PluginInterface

logger = get_logger()


class PluginManager:
    def __init__(self, plugin_dir: str, config_file: str) -> None:
        self.plugin_dir = plugin_dir
        self.config_file = config_file
        self.plugins: dict[str, PluginInterface] = {}
        self.config: dict[str, dict[str, Any]] = {}

    async def load_plugins(self) -> None:
        """Load and initialize all plugins."""
        self._load_config()
        for filename in Path(self.plugin_dir).iterdir():
            if filename.suffix == ".py" and not filename.name.startswith("__"):
                plugin_name = filename.stem
                if plugin_name in self.config and self.config[plugin_name].get("enabled", True):
                    await self._load_plugin(plugin_name)

    def _load_config(self) -> None:
        """Load the plugin configuration."""
        try:
            with Path(self.config_file).open() as f:
                self.config = json.load(f)
        except FileNotFoundError:
            logger.warning("Config file %s not found. Using default configurations.", self.config_file)
            self.config = {}

    async def _load_plugin(self, plugin_name: str) -> None:
        """Load a single plugin."""
        try:
            module = importlib.import_module(f"plugins.{plugin_name}")
            plugin_class: type[PluginInterface] = getattr(module, f"{plugin_name.capitalize()}Plugin")
            plugin = plugin_class()
            await plugin.initialize()
            self.plugins[plugin_name] = plugin
            logger.info("Loaded plugin: %s", plugin_name)
        except Exception:
            logger.exception("Failed to load plugin %s", plugin_name)

    async def cleanup_plugins(self) -> None:
        """Clean up all plugins."""
        await asyncio.gather(*(plugin.cleanup() for plugin in self.plugins.values()))

    async def handle_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        """Distribute an event to all plugins."""
        await asyncio.gather(*(plugin.handle_event(event_type, event_data) for plugin in self.plugins.values()))

    async def pre_decision(self, context: dict[str, Any]) -> dict[str, Any]:
        """Run pre-decision hooks for all plugins."""
        results = await asyncio.gather(*(plugin.pre_decision(context) for plugin in self.plugins.values()))
        return {k: v for d in results for k, v in d.items()}

    async def post_decision(self, decision: dict[str, Any], context: dict[str, Any]) -> None:
        """Run post-decision hooks for all plugins."""
        await asyncio.gather(*(plugin.post_decision(decision, context) for plugin in self.plugins.values()))
