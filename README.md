# webTalk - Your AI Web Assistant 🌐

webTalk is a powerful Python tool that lets AI navigate websites and complete tasks for you. Think of it as your personal web assistant that can handle repetitive online tasks while you focus on more important things, similar to Anthropic's computer use capability but specifically for in-browser use.

## ✨ What Makes webTalk Special?

- **Simple to Use**: Just tell it what you want in plain English
- **Smart Navigation**: Uses GenAI to understand web pages like a human would
- **Visual Feedback**: Shows you exactly what it's doing (optional)
- **Plugin System**: Easily add new features to make it even more powerful (currently features Bitwarden integration for secure logins!)

## 🚀 Quick Example

```bash
python main.py "Go to amazon.com, search for headphones under $50, and open the highest-rated one"
```

That's it! webTalk will handle all the clicking, scrolling, and searching for you.

## 📦 Installation

1. Clone this project:
```bash
git clone https://github.com/yourusername/webTalk.git
cd webTalk
```

2. Install what you need:
```bash
pip install -r requirements.txt
playwright install
```

3. Add your OpenAI API key to a `.env` file:
```bash
OPENAI_API_KEY=your_api_key_here
```

## 💡 What Can You Do With It?

- Search and compare products across websites
- Fill out forms automatically
- Check prices across different stores
- Log into your accounts securely (via Bitwarden)
- Monitor websites for changes
- And much more!

## ⚙️ Options You Can Use

- `--method xpath`: Choose how to find things on the page (xpath or ocr)
- `--show-visuals`: See what the AI is doing on the page
- `--verbose`: Get more detailed information
- `--model`: Pick your AI model (currently supporting OpenAI or Groq)

## 🛠️ Want to Make It Better?

We love help! If you want to improve webTalk:
1. Fork the project
2. Create your feature branch
3. Make your changes
4. Send us a pull request

*Got questions? Open an issue - we're here to help!*

## 🚧 Coming Soon

- Support for more AI models
- Vision component implementation (beyond XPath)
- Performance optimization through caching
- User-friendly GUI for real-time interaction
- New plugins in development:
  - memGPT integration
  - Proxy manager
  - Email integration

---

*Interested in contributing to any of our upcoming features? I'd love your help!*
