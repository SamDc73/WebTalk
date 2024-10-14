import asyncio
import json
import os
import subprocess
from typing import Any
from urllib.parse import urlparse

from plugins.plugin_interface import PluginInterface
from utils import get_logger


logger = get_logger()


class BitwardenPlugin(PluginInterface):
    async def initialize(self) -> None:
        self.session_key = os.getenv("BW_SESSION")
        if not self.session_key:
            logger.error("BW_SESSION environment variable is not set")
        else:
            await self.check_login_status()

    async def cleanup(self) -> None:
        pass

    async def handle_event(self, event_type: str, event_data: dict[str, Any]) -> None:
        if event_type == "navigation":
            logger.debug("Bitwarden plugin: Navigated to %s", event_data["url"])

    async def pre_decision(self, context: dict[str, Any]) -> dict[str, Any]:
        if self.detect_login_form(context["elements"]):
            credentials = await self.get_credentials(context.get("url", ""))
            if credentials:
                return {"credentials": credentials}
        return {}

    async def post_decision(self, decision: dict[str, Any], context: dict[str, Any]) -> None:
        # We don't need to do anything after a decision is made in this plugin
        pass

    async def check_login_status(self) -> None:
        try:
            result = await self.run_command(["bw", "status"])
            status = json.loads(result)
            if status["status"] == "unlocked":
                logger.info("Successfully connected to Bitwarden")
            else:
                logger.warning("Unexpected Bitwarden status: %s", status["status"])
        except Exception:
            logger.exception("Failed to check Bitwarden status")

    async def get_credentials(self, url: str) -> dict[str, str] | None:
        if not self.session_key:
            logger.warning("BW_SESSION not set. Cannot retrieve credentials.")
            return None

        if not url:
            logger.warning("No URL provided for credential lookup.")
            return None

        domain = self.extract_domain(url)
        try:
            result = await self.run_command(["bw", "list", "items", "--url", domain])
            items = json.loads(result)
            if items:
                item = items[0]  # Assume the first item is the one we want
                if "login" in item and "username" in item["login"] and "password" in item["login"]:
                    return {"username": item["login"]["username"], "password": item["login"]["password"]}
            # If we reach this point, no credentials were found
            return None
        except Exception:
            logger.exception("Failed to get credentials for %s", domain)
            return None
        else:
            if "items" not in locals() or not items:
                logger.warning("No credentials found for %s", domain)

    @staticmethod
    def detect_login_form(elements: dict[int, dict[str, Any]]) -> bool:
        has_username = any(
            "username" in e["description"].lower() or "email" in e["description"].lower() for e in elements.values()
        )
        has_password = any("password" in e["description"].lower() for e in elements.values())
        return has_username and has_password

    @staticmethod
    def extract_domain(url: str) -> str:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        return domain[4:] if domain.startswith("www.") else domain

    @staticmethod
    async def run_command(command: list[str]) -> str:
        env = os.environ.copy()
        env["BW_SESSION"] = os.getenv("BW_SESSION", "")
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=env,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        return stdout.decode().strip()
