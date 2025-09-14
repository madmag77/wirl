# News Digest Workflow

This workflow collects recent news from preset resources—a mix of RSS feeds and standard web pages—summarizes the updates with a local LLM and delivers the digest via email or Telegram.

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

## Running

Activate the virtual environment and execute the workflow:

```bash
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/news_digest_workflow/news_digest_workflow.wirl \
  --functions workflow_definitions.news_digest_workflow.news_digest_workflow \
  --param trigger=run
```

The workflow fetches news from the predefined sources, summarizes new items from the last seven days, and sends the digest via the configured channel.
The delivery type (email or telegram) and the recipient address are set in the `SendSummary` node's constants within the WIRL definition.
