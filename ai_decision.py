class AIDecisionMaker:
    def __init__(self, client, model):
        self.client = client
        self.model = model

    async def make_decision(self, mapped_elements, task, current_url):
        elements_description = "\n".join(
            [f"{num}: {info['description']}" for num, info in mapped_elements.items()]
        )

        full_prompt = f"""Task: {task}
    Current URL: {current_url}
    Page elements:
    {elements_description}

    Decide the next action:
    - To click an element, respond with just the element number.
    - To input text, respond with the element number followed by a colon and the text to input.
    - If the task is complete, respond with "DONE".

    Your decision:"""

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": full_prompt}]
            )
            decision = response.choices[0].message.content.strip()
            print(f"AI Decision: {decision}")
            return decision
        except Exception as e:
            print(f"Error with OpenAI model: {e}")
            return None

    def parse_decision(self, decision):
        if decision.upper() == "DONE":
            return None

        parts = decision.split(':', 1)
        try:
            element = int(parts[0])
            if len(parts) > 1:
                return {"type": "input", "element": element, "text": parts[1].strip()}
            else:
                return {"type": "click", "element": element}
        except ValueError:
            print(f"Invalid decision: {decision}")
            return None
