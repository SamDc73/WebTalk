from model_manager import ModelManager
from utils import get_logger


class DecisionMaker:
    def __init__(self, model_manager: ModelManager, verbose: bool) -> None:
        """
        Initialize the DecisionMaker.

        Parameters
        ----------
        model_manager : ModelManager
            The model manager for AI completions.
        logger : object
            The logger instance.
        verbose : bool
            Whether to log debug information.
        """
        self.logger = get_logger()
        self.model_manager = model_manager
        self.verbose = verbose

    async def make_decision(
        self, mapped_elements: dict[int, dict[str, object]], task: str, current_url: str
    ) -> str | None:
        """
        Make a decision based on the current page elements and task.

        Parameters
        ----------
        mapped_elements : Dict[int, Dict[str, object]]
            A dictionary of mapped elements on the page.
        task : str
            The current task to be performed.
        current_url : str
            The current URL of the page.

        Returns
        -------
        Optional[str]
            The AI's decision as a string, or None if an error occurred.
        """
        elements_description = "\n".join(
            f"{num}: {info['description']} ({info['type']})" for num, info in mapped_elements.items()
        )

        prompt = f"""Task: {task}
Current URL: {current_url}
Page elements:
{elements_description}

Decide the next action:
- To click an element, respond with just the element number.
- To input text, respond with the element number followed by a colon and the text to input.
- To press Enter after inputting text, respond with the element number, colon, text, and then "ENTER".
- If the task is complete, respond with "DONE".

Your decision:"""

        try:
            decision = await self.model_manager.get_completion(
                [
                    {
                        "role": "system",
                        "content": "You are an AI assistant that navigates web pages."
                        "Be decisive and avoid repeating actions.",
                    },
                    {"role": "user", "content": prompt},
                ]
            )
            if self.verbose:
                self.logger.debug(f"AI Decision: {decision}")
            return decision
        except Exception as e:
            self.logger.error(f"Error with AI model: {e}")
            return None

    def parse_decision(self, decision: str) -> dict[str, object] | None:
        """
        Parse the AI's decision into an actionable format.

        Parameters
        ----------
        decision : str
            The decision string from the AI.

        Returns
        -------
        Optional[Dict[str, object]]
            A dictionary representing the parsed decision, or None if the decision is invalid or the task is complete.
        """
        if decision.upper() == "DONE":
            return None

        parts = decision.split(":", 1)
        try:
            element = int(parts[0])
            if len(parts) > 1:
                text = parts[1].strip()
                if text.upper().endswith("ENTER"):
                    return {
                        "type": "input_enter",
                        "element": element,
                        "text": text[:-5].strip(),
                    }
                return {"type": "input", "element": element, "text": text}
            return {"type": "click", "element": element}
        except ValueError:
            self.logger.error(f"Invalid decision: {decision}")
            return None
