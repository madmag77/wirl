def get_next_resource(resources: list | None, initial_resources_to_process: list, config: dict) -> dict:
    resources_to_process = resources or initial_resources_to_process
    if not resources_to_process:
        return {"no_resources_to_process": True}
    res = resources_to_process.pop(0)
    return {"resource": res, "remaining_resources": resources_to_process}


def fetch_news(resource: dict, config: dict) -> dict:
    return {"news_items": [{"title": "t", "summary": "s", "link": "", "published": None}]}


def collect_news(
    remaining_resources_to_process: list,
    news_items: list | None,
    no_resources_to_process: bool,
    config: dict,
) -> dict:
    if no_resources_to_process:
        return {"is_done": True, "news_items": []}
    return {"is_done": len(remaining_resources_to_process) == 0, "news_items": news_items}


def summarize_news(news_items: list, config: dict) -> dict:
    return {"summary": "weekly summary"}


def send_email(summary: str, config: dict) -> dict:
    return {"success": True}


FN_MAP = {
    "get_next_resource": get_next_resource,
    "fetch_news": fetch_news,
    "collect_news": collect_news,
    "summarize_news": summarize_news,
    "send_email": send_email,
}


def test_news_digest_e2e():
    result = run_workflow(
        fn_map=FN_MAP,
        params={"resources": [{"url": "u", "type": "web"}]},
    )
    assert result["SummarizeNews.summary"] == "weekly summary"


def run_workflow(fn_map: dict, params: dict) -> dict:
    resources = params["resources"]
    remaining = None
    collected: list = []
    while True:
        res = fn_map["get_next_resource"](remaining, resources, {})
        remaining = res.get("remaining_resources")
        if res.get("no_resources_to_process"):
            collect = fn_map["collect_news"](remaining, None, True, {})
            collected.extend(collect["news_items"])
            break
        news = fn_map["fetch_news"](res["resource"], {})
        collect = fn_map["collect_news"](remaining, news["news_items"], False, {})
        collected.extend(collect["news_items"])
        if collect["is_done"]:
            break
        resources = []  # resources already initialized
    summary = fn_map["summarize_news"](collected, {})["summary"]
    fn_map["send_email"](summary, {})
    return {"SummarizeNews.summary": summary}

