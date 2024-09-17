def format_url(url):
    if not url.startswith(("http://", "https://")):
        return "https://" + url
    return url

async def parse_initial_message(client, model, message):
    try:
        response = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are an AI assistant that extracts the website URL and task from a given message. Respond with only the URL and task, separated by a newline."},
                {"role": "user", "content": message}
            ]
        )
        url, task = response.choices[0].message.content.strip().split('\n')
        return url.strip(), task.strip()
    except Exception as e:
        print(f"Error parsing initial message: {e}")
        return None, None
