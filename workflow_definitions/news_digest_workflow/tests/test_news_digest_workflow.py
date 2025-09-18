from wirl_pregel_runner import run_workflow

def get_next_resource(resources: list | None, initial_resources_to_process: list, config: dict) -> dict:
    resources_to_process = resources or initial_resources_to_process
    if not resources_to_process:
        return {"no_resources_to_process": True}
    res = resources_to_process.pop(0)
    return {"resource": res, "remaining_resources": resources_to_process}


def fetch_news(resource: dict, config: dict) -> dict:
    return {"fetched_items": [{"title": "t", "summary": "s", "link": "", "published": None}]}


def collect_news(
    remaining_resources_to_process: list,
    fetched_items: list | None,
    no_resources_to_process: bool,
    config: dict,
) -> dict:
    if no_resources_to_process:
        return {"is_done": True, "news_items": []}
    return {"is_done": len(remaining_resources_to_process) == 0, "news_items": fetched_items}


def summarize_news(news_items: list, config: dict) -> dict:
    return {"summary": "weekly summary"}


def send_summary(summary: str, config: dict) -> dict:
    return {"success": True}


FN_MAP = {
    "get_next_resource": get_next_resource,
    "fetch_news": fetch_news,
    "collect_news": collect_news,
    "summarize_news": summarize_news,
    "send_summary": send_summary,
}


def test_news_digest_e2e():
    result = run_workflow(
        "workflow_definitions/news_digest_workflow/news_digest_workflow.wirl",
        fn_map=FN_MAP,
        params={
            "resources": [{"url": "u", "type": "web"}],
        },
    )

    assert result["SummarizeNews.summary"] == "weekly summary"
