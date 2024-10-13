import asyncio
import json
import subprocess
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import urlparse

from plugins.base_plugin import BasePlugin
from utils import get_logger


class BitwardenPlugin(BasePlugin):
    def __init__(self) -> None:
        self.logger = get_logger()
        self.is_logged_in = False
        self.session_key = None

    async def initialize(self) -> None:
        self.logger.info("Initializing Bitwarden plugin")
        await self.check_login_status()

    async def cleanup(self) -> None:
        self.logger.info("Cleaning up Bitwarden plugin")
        if self.session_key:
            await self.lock_vault()

    async def check_login_status(self) -> None:
        self.logger.info("Checking Bitwarden login status")
        try:
            result = await self.run_command(["bw", "status"])
            status = json.loads(result)
            if status["status"] == "unauthenticated":
                self.logger.warning("Not logged in to Bitwarden")
                self.is_logged_in = False
            elif status["status"] == "locked":
                self.logger.warning("Bitwarden vault is locked")
                await self.unlock_vault()
            else:
                self.logger.info("Successfully logged in to Bitwarden")
                self.is_logged_in = True
        except Exception as e:
            self.logger.exception(f"Failed to check Bitwarden status: {e}")
            self.is_logged_in = False

    async def unlock_vault(self) -> None:
        try:
            result = await self.run_command(["bw", "unlock", "--raw"])
            self.session_key = result.strip()
            self.is_logged_in = True
            self.logger.info("Bitwarden vault unlocked successfully")
        except Exception as e:
            self.logger.exception(f"Failed to unlock Bitwarden vault: {e}")

    async def lock_vault(self) -> None:
        try:
            await self.run_command(["bw", "lock"])
            self.session_key = None
            self.is_logged_in = False
            self.logger.info("Bitwarden vault locked successfully")
        except Exception as e:
            self.logger.exception(f"Failed to lock Bitwarden vault: {e}")

    async def get_credentials(self, url: str) -> dict[str, str] | None:
        self.logger.info(f"Attempting to get credentials for {url}")
        if not self.is_logged_in:
            self.logger.warning("Not logged in to Bitwarden. Cannot retrieve credentials.")
            return None

        domain = self.extract_domain(url)
        url_formats = [f"https://www.{domain}", f"https://{domain}", domain, url]

        for format in url_formats:
            try:
                self.logger.info(f"Trying to fetch credentials for: {format}")
                result = await self.run_command(["bw", "get", "item", format, f"--session={self.session_key}"])
                item = json.loads(result)
                if "login" in item and "username" in item["login"] and "password" in item["login"]:
                    self.logger.info(f"Successfully retrieved credentials for {format}")
                    return {"username": item["login"]["username"], "password": item["login"]["password"]}
            except Exception as e:
                self.logger.warning(f"Failed to get credentials for {format}: {e}")

        self.logger.error(f"No credentials found for {url} after trying multiple formats")
        return None

    async def on_navigation(self, url: str) -> None:
        self.logger.debug(f"Bitwarden plugin: Navigated to {url}")

    async def on_element_detection(self, elements: Mapping[int, Mapping[str, Any]]) -> None:
        self.logger.debug("Bitwarden plugin: Elements detected")

    async def pre_decision(
        self, mapped_elements: Mapping[int, Mapping[str, Any]], current_url: str,
    ) -> tuple[bool, str | None]:
        self.logger.debug(f"Bitwarden plugin: Pre-decision for {current_url}")
        if self.detect_login_form(mapped_elements):
            self.logger.info("Login form detected")
            credentials = await self.get_credentials(current_url)
            if credentials:
                action = self.fill_credentials(mapped_elements, credentials)
                self.logger.info("Credentials found and action prepared")
                return True, action
            self.logger.warning("No credentials found for this URL")
        return False, None

    def detect_login_form(self, elements: Mapping[int, Mapping[str, Any]]) -> bool:
        self.logger.debug("Detecting login form")
        has_username = any(
            "username" in e["description"].lower() or "email" in e["description"].lower() for e in elements.values()
        )
        has_password = any("password" in e["description"].lower() for e in elements.values())
        result = has_username and has_password
        self.logger.debug(f"Login form detected: {result}")
        return result

    def fill_credentials(self, elements: Mapping[int, Mapping[str, Any]], credentials: Mapping[str, str]) -> str:
        self.logger.info("Preparing to fill credentials")
        actions = []
        for idx, element in elements.items():
            if "username" in element["description"].lower() or "email" in element["description"].lower():
                actions.append(f"{idx}:{credentials['username']}")
            elif "password" in element["description"].lower():
                actions.append(f"{idx}:{credentials['password']}")
        actions.append("submit")
        self.logger.info("Credentials fill action prepared")
        return ";".join(actions)

    async def pre_action(
        self, action: Mapping[str, Any], mapped_elements: Mapping[int, Mapping[str, Any]],
    ) -> Mapping[str, Any]:
        self.logger.debug(f"Bitwarden plugin: Pre-action for {action['type']}")
        if action["type"] in ["input", "input_enter"]:
            element_description = mapped_elements[action["element"]]["description"].lower()
            if "password" in element_description:
                credentials = await self.get_credentials(action.get("url", ""))
                if credentials:
                    action = dict(action)
                    action["text"] = credentials["password"]
                    self.logger.info("Password filled by Bitwarden")
        return action

    async def post_action(self, action: Mapping[str, Any], success: bool) -> None:
        self.logger.debug(f"Bitwarden plugin: Post-action. Success: {success}")

    async def on_error(self, error: Exception) -> None:
        self.logger.error(f"Bitwarden plugin error: {error}")

    @staticmethod
    def extract_domain(url: str) -> str:
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        return domain[4:] if domain.startswith("www.") else domain

    @staticmethod
    async def run_command(command: Sequence[str]) -> str:
        process = await asyncio.create_subprocess_exec(
            *command, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, command, stdout, stderr)
        return stdout.decode().strip()
