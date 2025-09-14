import os
from datetime import datetime, timedelta
from email.message import EmailMessage
import logging
import smtplib
from enum import Enum
from urllib.parse import urljoin

import feedparser
import requests
from bs4 import BeautifulSoup
from dateutil import parser as dateparser
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)


class ResourceType(str, Enum):
    RSS = "rss"
    WEB = "web"


class NewsResource(BaseModel):
    url: str = Field(description="Resource URL")
    type: ResourceType = Field(description="Type of the resource")


class NewsItem(BaseModel):
    title: str = Field(description="Title of the news item")
    link: str = Field(description="Link to the news item")
    published: datetime = Field(description="Publication datetime")
    summary: str = Field(description="Summary or excerpt of the item", default="")


def get_resources(trigger: str, config: dict) -> dict:
    resources = [
        {"url": "https://karpathy.bearblog.dev/rss", "type": ResourceType.RSS},
        {"url": "https://www.anthropic.com/news", "type": ResourceType.WEB},
        {"url": "https://openai.com/news/research/", "type": ResourceType.WEB},
    ]
    return {"resources": [NewsResource(**r) for r in resources]}


def fetch_news(resources: list[NewsResource], config: dict) -> dict:
    days_back = config.get("days_back", 7)
    start_date = datetime.utcnow() - timedelta(days=days_back)
    news_items: list[NewsItem] = []
    headers = {"User-Agent": "Mozilla/5.0"}

    for res in resources:
        try:
            if res.type == ResourceType.RSS:
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
                        NewsItem(
                            title=entry.get("title", ""),
                            link=entry.get("link", ""),
                            published=published,
                            summary=summary,
                        )
                    )
            elif res.type == ResourceType.WEB:
                resp = requests.get(res.url, headers=headers, timeout=10)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.find_all("a"):
                    href = a.get("href")
                    text = a.get_text(" ", strip=True)
                    if not href or not text:
                        continue
                    context = a.parent.get_text(" ", strip=True)
                    try:
                        published = dateparser.parse(context, fuzzy=True)
                    except Exception:
                        continue
                    if published < start_date:
                        continue
                    link = urljoin(res.url, href)
                    summary = ""
                    try:
                        article = requests.get(link, headers=headers, timeout=10)
                        art_soup = BeautifulSoup(article.text, "html.parser")
                        summary = " ".join(art_soup.get_text(" ", strip=True).split())[:500]
                    except Exception:
                        pass
                    news_items.append(
                        NewsItem(title=text, link=link, published=published, summary=summary)
                    )
        except Exception as e:
            logger.warning(f"Failed to parse {res.url}: {e}")

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
    return {"summary": summary}


def send_email(summary: str, config: dict) -> dict:
    smtp_server = os.environ.get("SMTP_SERVER")
    smtp_port = int(os.environ.get("SMTP_PORT", "587"))
    smtp_username = os.environ.get("SMTP_USERNAME")
    smtp_password = os.environ.get("SMTP_PASSWORD")
    from_email = os.environ.get("FROM_EMAIL")
    to_email = os.environ.get("TO_EMAIL")

    msg = EmailMessage()
    msg["Subject"] = "Weekly News Digest"
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(summary)

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            if smtp_username and smtp_password:
                server.login(smtp_username, smtp_password)
            server.send_message(msg)
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        raise e

    return {"success": True}

