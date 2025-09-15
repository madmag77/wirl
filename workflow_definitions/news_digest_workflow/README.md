# News Digest Workflow

This workflow collects recent news from a list of resources—a mix of RSS feeds and standard web pages—summarizes the updates with a local LLM and emails the digest.

## Setup

Install dependencies (once):

```bash
make workflows-setup  # or install only this workflow's requirements
uv pip install --python .venv/bin/python -r workflow_definitions/news_digest_workflow/requirements.txt
```

Create a `.env` file with email and model settings:

```
OPENAI_API_KEY=sk-...            # used by ChatOpenAI
SMTP_SERVER=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your_username      # optional
SMTP_PASSWORD=your_password      # optional
FROM_EMAIL=sender@example.com
TO_EMAIL=recipient@example.com
```

## Running

Activate the virtual environment and execute the workflow:

```bash
python -m wirl_pregel_runner.pregel_runner \
  workflow_definitions/news_digest_workflow/news_digest_workflow.wirl \
  --functions workflow_definitions.news_digest_workflow.news_digest_workflow \
  --param 'resources=[{"url":"https://example.com/feed","type":"rss"}]'
```

The workflow fetches news from the provided sources, summarizes new items from the last seven days, and sends the digest via email.
