import json
import subprocess
from typing import Any
from urllib.parse import urlparse

from plugins.base_plugin import BasePlugin
from utils import get_logger


class BitwardenPlugin(BasePlugin):
    def __init__(self) -> None:
        self.logger = get_logger()
        self.is_logged_in = False

    def initialize(self) -> None:
        self.logger.info("Initializing Bitwarden plugin")
        self.check_login_status()

    def cleanup(self) -> None:
        self.logger.info("Cleaning up Bitwarden plugin")

    def check_login_status(self) -> None:
        self.logger.info("Checking Bitwarden login status")
        try:
            result = subprocess.run(["bw", "status"], capture_output=True, text=True, check=True)
            status = json.loads(result.stdout)
            if status["status"] == "unauthenticated":
                self.logger.warning("Not logged in to Bitwarden")
                self.is_logged_in = False
            elif status["status"] == "locked":
                self.logger.warning("Bitwarden vault is locked")
                self.is_logged_in = False
            else:
                self.logger.info("Successfully logged in to Bitwarden")
                self.is_logged_in = True
        except subprocess.CalledProcessError as e:
            self.logger.exception(f"Failed to check Bitwarden status: {e}")
            self.is_logged_in = False
        except json.JSONDecodeError as e:
            self.logger.exception(f"Failed to parse Bitwarden status: {e}")
            self.is_logged_in = False

    def get_credentials(self, url: str) -> dict[str, str] | None:
        self.logger.info(f"Attempting to get credentials for {url}")
        if not self.is_logged_in:
            self.logger.warning("Not logged in to Bitwarden. Cannot retrieve credentials.")
            return None

        # Parse the URL and extract the domain
        parsed_url = urlparse(url)
        domain = parsed_url.netloc
        if domain.startswith("www."):
            domain = domain[4:]

        # Try different URL formats
        url_formats = [f"https://www.{domain}", f"https://{domain}", domain, url]

        for format in url_formats:
            try:
                self.logger.info(f"Trying to fetch credentials for: {format}")
                result = subprocess.run(["bw", "get", "item", format], capture_output=True, text=True, check=True)
                item = json.loads(result.stdout)
                if "login" in item and "username" in item["login"] and "password" in item["login"]:
                    self.logger.info(f"Successfully retrieved credentials for {format}")
                    return {"username": item["login"]["username"], "password": item["login"]["password"]}
            except subprocess.CalledProcessError as e:
                self.logger.warning(f"Failed to get credentials for {format}: {e}")
            except json.JSONDecodeError as e:
                self.logger.warning(f"Failed to parse Bitwarden output for {format}: {e}")

        self.logger.error(f"No credentials found for {url} after trying multiple formats")
        return None


    def on_navigation(self, url: str) -> None:
        self.logger.info(f"Bitwarden plugin: Navigated to {url}")

    def on_element_detection(self, elements: dict[int, dict[str, Any]]) -> None:
        self.logger.debug("Bitwarden plugin: Elements detected")

    def pre_decision(self, mapped_elements: dict[int, dict[str, Any]], current_url: str) -> tuple[bool, str | None]:
        self.logger.info(f"Bitwarden plugin: Pre-decision for {current_url}")
        login_form = self.detect_login_form(mapped_elements)
        if login_form:
            self.logger.info("Login form detected")
            credentials = self.get_credentials(current_url)
            if credentials:
                action = self.fill_credentials(mapped_elements, credentials)
                self.logger.info("Credentials found and action prepared")
                return True, action
            self.logger.warning("No credentials found for this URL")
        else:
            self.logger.debug("No login form detected")
        return False, None

    def detect_login_form(self, elements: dict[int, dict[str, Any]]) -> bool:
        self.logger.debug("Detecting login form")
        has_username = any(
            "username" in e["description"].lower() or "email" in e["description"].lower() for e in elements.values()
        )
        has_password = any("password" in e["description"].lower() for e in elements.values())
        result = has_username and has_password
        self.logger.info(f"Login form detected: {result}")
        return result

    def fill_credentials(self, elements: dict[int, dict[str, Any]], credentials: dict[str, str]) -> str:
        self.logger.info("Preparing to fill credentials")
        action = ""
        for idx, element in elements.items():
            if "username" in element["description"].lower() or "email" in element["description"].lower():
                action += f"{idx}:{credentials['username']}\n"
                self.logger.debug(f"Username field identified: {idx}")
            elif "password" in element["description"].lower():
                action += f"{idx}:{credentials['password']}\n"
                self.logger.debug(f"Password field identified: {idx}")
        action += "submit"  # Assuming there's a submit button
        self.logger.info("Credentials fill action prepared")
        return action.strip()

    async def pre_action(self, action: dict, mapped_elements: dict) -> dict:
        self.logger.info(f"Bitwarden plugin: Pre-action for {action['type']}")
        if action["type"] in ["input", "input_enter"]:
            credentials = self.get_credentials("https://www.linkedin.com")
            if credentials:
                element_description = mapped_elements[action["element"]]["description"].lower()
                if "email" in element_description or "username" in element_description:
                    action["text"] = credentials["username"]
                    self.logger.info("Username filled by Bitwarden")
                elif "password" in element_description:
                    action["text"] = credentials["password"]
                    self.logger.info("Password filled by Bitwarden")
        return action

    async def post_action(self, action: dict, success: bool) -> None:
        self.logger.info(f"Bitwarden plugin: Post-action. Success: {success}")

    async def on_error(self, error: Exception) -> None:
        self.logger.error(f"Bitwarden plugin error: {error}")
