class DecisionMaker:
    def __init__(self, client, model, logger, verbose):
        self.client = client
        self.model = model
        self.logger = logger
        self.verbose = verbose

    async def make_decision(self, mapped_elements, task, current_url):
        elements_description = "\n".join(
            [f"{num}: {info['description']} ({info['type']})" for num, info in mapped_elements.items()]
        )

        full_prompt = f"""Task: {task}
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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an AI assistant that navigates web pages. Be decisive and avoid repeating actions."},
                    {"role": "user", "content": full_prompt}
                ]
            )
            decision = response.choices[0].message.content.strip()
            if self.verbose:
                self.logger.debug(f"AI Decision: {decision}")
            return decision
        except Exception as e:
            self.logger.error(f"Error with OpenAI model: {e}")
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

