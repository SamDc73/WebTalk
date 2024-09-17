# Autonomous Web AI

Autonomous Web AI is a Python tool that uses AI to navigate web pages and complete tasks autonomously.

## Installation

1. Clone this repository:
   ```
   git clone https://github.com/yourusername/webTalk.git
   cd webTalk
   ```

2. Install requirements:
   ```
   pip install -r requirements.txt
   ```

3. Install Playwright browsers:
   ```
   playwright install
   ```

4. Set up your OpenAI API key in the `.env` file:
   ```
   OPENAI_API_KEY=your_api_key_here
   ```

## Usage

Run the main script with your desired task:

```
python main.py "Your task description here" [options]
```

### Options:
- `--method`: Choose element detection method (xpath or ocr). Default is xpath.
- `--show-visuals`: Display visual markers on the page.

### Example:
```
python main.py "Go to amazon search for iphone 13 open the first product where the price is less than 500 then add to cart" --method xpath --show-visuals
```

