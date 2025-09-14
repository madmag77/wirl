import os
from datetime import datetime, timedelta
from email.message import EmailMessage
import smtplib
import feedparser
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
import logging
import dotenv

logger = logging.getLogger(__name__)

dotenv.load_dotenv()


class NewsResource(BaseModel):
    url: str = Field(description="Resource URL")
    type: str = Field(description="Type of the resource e.g. web, twitter")


class NewsItem(BaseModel):
    title: str = Field(description="Title of the news item")
    link: str = Field(description="Link to the news item")
    published: datetime = Field(description="Publication datetime")
    summary: str = Field(description="Summary or excerpt of the item", default="")


def get_resources(trigger: str, config: dict) -> dict:
    resources = [
        {"url": "https://karpathy.bearblog.dev/feed/", "type": "web"},
        {"url": "https://www.anthropic.com/news", "type": "web"},
        {"url": "https://openai.com/news/research/", "type": "web"},
    ]
    return {"resources": [NewsResource(**r) for r in resources]}


def fetch_news(resources: list[NewsResource], config: dict) -> dict:
    days_back = config.get("days_back", 180)
    start_date = datetime.utcnow() - timedelta(days=days_back)
    news_items: list[NewsItem] = []

    for res in resources:
        if res.type != "web":
            continue
        feed = feedparser.parse(res.url)
        for entry in getattr(feed, "entries", []):
            published_parsed = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
            if not published_parsed:
                continue
            published = datetime(*published_parsed[:6])
            if published < start_date:
                continue
            summary = entry.get("summary", "")
            news_items.append(
                NewsItem(title=entry.get("title", ""),
                         link=entry.get("link", ""),
                         published=published,
                         summary=summary)
            )
    print(news_items)
    return {"news_items": news_items}


def summarize_news(news_items: list[NewsItem], config: dict) -> dict:
    model = config.get("model")
    base_url = config.get("base_url")
    temperature = config.get("temperature", 0)

    llm = ChatOpenAI(
        model=model,
        base_url=base_url,
        temperature=temperature,
        api_key=os.getenv("OPENAI_API_KEY", "sk"),
    )

    if not news_items:
        return {"summary": "No new items."}

    text = "\n\n".join([f"{item.title}: {item.summary}" for item in news_items])
    response = llm.invoke(f"Provide a concise summary of the following news items:\n{text}")
    summary = getattr(response, "content", str(response))
    print(summary)
    return {"summary": summary}


def send_email(summary: str, config: dict) -> dict:
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    from_email = os.environ.get("FROM_EMAIL")
    to_email = os.environ.get("TO_EMAIL")

    # Validate required environment variables
    if not smtp_server:
        raise ValueError("SMTP_SERVER environment variable is required")
    if not from_email:
        raise ValueError("FROM_EMAIL environment variable is required")
    if not to_email:
        raise ValueError("TO_EMAIL environment variable is required")

    msg = EmailMessage()
    msg["Subject"] = "Weekly News Digest"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content("Here is the news digest:\n\n" + summary)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.ehlo()  # Identify ourselves to the server
            server.starttls()  # Enable TLS encryption
            server.ehlo()  # Re-identify ourselves after TLS
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)
        logger.info("Email sent successfully")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise e

    return {"success": True}
