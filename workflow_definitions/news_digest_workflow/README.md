# News Digest Workflow

This workflow collects recent news from a list of resources—a mix of RSS feeds and standard web pages—summarizes the updates with a local LLM and delivers the digest via email or Telegram.

## Setup

Install dependencies (once):

```bash
make workflows-setup  # or install only this workflow's requirements
uv pip install --python .venv/bin/python -r workflow_definitions/news_digest_workflow/requirements.txt
```

Create a `.env` file with delivery and model settings:

```
OPENAI_API_KEY=sk-...            # used by ChatOpenAI
SMTP_SERVER=smtp.example.com     # required for email
SMTP_PORT=587
SMTP_USERNAME=your_username      # optional
SMTP_PASSWORD=your_password      # optional
FROM_EMAIL=sender@example.com    # required for email
TELEGRAM_BOT_TOKEN=123456:ABCDEF # required for telegram
```

### Setting up Telegram Bot

To use Telegram delivery, you need to create a Telegram bot and get your chat ID:

#### 1. Create a Telegram Bot with BotFather

1. Open Telegram and search for `@BotFather`
2. Start a chat with BotFather by clicking "Start" or sending `/start`
3. Create a new bot by sending `/newbot`
4. Follow the prompts:
   - Choose a name for your bot (e.g., "My News Digest Bot")
   - Choose a username for your bot (must end with "bot", e.g., "mynewsdigestbot")
5. BotFather will provide you with a bot token that looks like `123456789:ABCDEFghijklmnopqrstuvwxyz`
6. Copy this token and add it to your `.env` file as `TELEGRAM_BOT_TOKEN`

#### 2. Get Your Chat ID

After creating the bot, you need to get your chat ID to receive messages:

1. Start a chat with your newly created bot by searching for its username
2. Send any message to the bot (e.g., "Hello")
3. Run the following command to get your chat ID:

```bash
make get_telegram_chat_id
```

This command will return your chat ID (a number like `123456789`). Add this ID to your `.env` file as `TELEGRAM_CHAT_ID`.
Choose the type of transport as `email` or `telegram` in `const` section of you `SendSummary` node, like this
```
    const {
      type: "telegram"
    }
```


## Running

Activate the virtual environment and execute the workflow:

```bash
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/news_digest_workflow/news_digest_workflow.wirl \
  --functions workflow_definitions.news_digest_workflow.news_digest_workflow \
  --param 'resources=[{"url":"https://example.com/feed","type":"rss"}]'
```

The workflow fetches news from the provided sources, summarizes new items from the last seven days, and sends the digest via the configured channel.
The delivery type (email or telegram) and the recipient address are set in the `SendSummary` node's constants within the WIRL definition.
