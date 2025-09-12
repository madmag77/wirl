from wirl_pregel_runner import run_workflow


def get_resources(trigger: str, config: dict) -> dict:
    return {"resources": [{"url": "u", "type": "web"}]}


def fetch_news(resources: list, config: dict) -> dict:
    return {"news_items": [{"title": "t", "summary": "s", "link": "", "published": None}]}


def summarize_news(news_items: list, config: dict) -> dict:
    return {"summary": "weekly summary"}


def send_email(summary: str, config: dict) -> dict:
    return {"success": True}


FN_MAP = {
    "get_resources": get_resources,
    "fetch_news": fetch_news,
    "summarize_news": summarize_news,
    "send_email": send_email,
}


def test_news_digest_e2e():
    result = run_workflow(
        "workflow_definitions/news_digest_workflow/news_digest_workflow.wirl",
        fn_map=FN_MAP,
        params={"trigger": "run"},
    )
    assert result["SummarizeNews.summary"] == "weekly summary"
