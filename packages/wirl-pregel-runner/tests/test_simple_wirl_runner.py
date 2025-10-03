from wirl_pregel_runner import run_workflow

WIRL_PATH = "tests/wirls/sample.wirl"


def query_extender(query: str, config: dict) -> dict:
    return {"extended_query": "extended query"}


def retrieve_from_web(extended_query: str, config: dict) -> dict:
    return {"chunks": ["chunk for hello"], "need_filtering": False}


def filter_chunks(query: str, need_filtering: bool, chunks: list[str], config: dict) -> dict:
    assert config.get("metadata", {}).get("llm_model") == "gpt-4o"
    return {"filtered_chunks": ["chunk for hello"]}


def final_answer_generation(query: str, extended_query: str, need_filtering: bool, chunks: list[str], filtered_chunks_summary: str, config: dict) -> dict:
    assert query == "hello"
    assert extended_query == "extended query"
    assert not need_filtering
    assert chunks == ["chunk for hello"]
    assert filtered_chunks_summary is None

    return {"final_answer": "final answer from chunks"}


FN_MAP = {
    "query_extender": query_extender,
    "retrieve_from_web": retrieve_from_web,
    "filter_chunks": filter_chunks,
    "final_answer_generation": final_answer_generation,
}


def test_wirl_runner_ok():
    overrides = dict(FN_MAP)
    result = run_workflow(WIRL_PATH, fn_map=overrides, params={"query": "hello"})
    assert result.get("FinalAnswer.final_answer") == "final answer from chunks"
