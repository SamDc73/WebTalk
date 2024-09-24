from PIL import Image
import io
import base64

class VisionDecisionMaker:
    def __init__(self, model_manager, logger, verbose):
        self.model_manager = model_manager
        self.logger = logger
        self.verbose = verbose

    async def take_screenshot(self, page):
        screenshot = await page.screenshot()
        return Image.open(io.BytesIO(screenshot))

    def encode_image(self, image):
        buffered = io.BytesIO()
        image.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode('utf-8')

    async def make_decision(self, page, mapped_elements, task, current_url):
        screenshot = await self.take_screenshot(page)
        base64_image = self.encode_image(screenshot)

        elements_description = "\n".join(
            [f"{num}: {info['description']} ({info['type']})" for num, info in mapped_elements.items()]
        )

        prompt = f"""Task: {task}
Current URL: {current_url}
Page elements:
{elements_description}

Analyze the screenshot and decide the next action:
- To click an element, respond with just the element number.
- To input text, respond with the element number followed by a colon and the text to input.
- To press Enter after inputting text, respond with the element number, colon, text, and then "ENTER".
- If the task is complete, respond with "DONE".

Your decision:"""

        try:
            decision = await self.model_manager.get_completion([
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ])
            if self.verbose:
                self.logger.debug(f"Vision AI Decision: {decision}")
            return decision
        except Exception as e:
            self.logger.error(f"Error with Vision AI model: {e}")
            return None

    def parse_decision(self, decision):
        if decision.upper() == "DONE":
            return None

        parts = decision.split(':', 1)
        try:
            element = int(parts[0])
            if len(parts) > 1:
                text = parts[1].strip()
                if text.upper().endswith("ENTER"):
                    return {"type": "input_enter", "element": element, "text": text[:-5].strip()}
                else:
                    return {"type": "input", "element": element, "text": text}
            else:
                return {"type": "click", "element": element}
        except ValueError:
            self.logger.error(f"Invalid decision: {decision}")
            return None