from wirl_pregel_runner import run_workflow

WIRL_PATH = "tests/wirls/sample_with_cycle.wirl"


def query_extender(query: str, add_query_aspect: str, config: dict) -> dict:
    return {"extended_query": "extended query"}


def retrieve_from_web(extended_query: str, config: dict) -> dict:
    return {"chunks": ["chunk for hello"], "need_filtering": False}


def retrieve_from_web_with_filtering(extended_query: str, config: dict) -> dict:
    return {"chunks": ["chunk for hello"], "need_filtering": True}


def retrieve_results_check(chunks: list[str], config: dict) -> dict:
    return {"is_enough": True, "next_query_aspect": "next query aspect"}


def retrieve_results_check_twice(chunks: list[str], config: dict) -> dict:
    if len(chunks) > 1:
        return {"is_enough": True, "next_query_aspect": "next query aspect"}
    return {"is_enough": False, "next_query_aspect": "next query aspect"}


def retrieve_results_check_false(chunks: list[str], config: dict) -> dict:
    return {"is_enough": False, "next_query_aspect": "next query aspect"}


def filter_chunks(query: str, need_filtering: bool, chunks: list[str], config: dict) -> dict:
    assert config.get("llm_model") == "gpt-4o"
    return {"filtered_chunks": ["filtered chunk for hello"], "filtered_chunks_summary": "filtered chunks summary"}


def final_answer_generation(query: str, need_filtering: bool, filtered_chunks: list[str], retrieved_chunks: list[str], filtered_chunks_summary: str, config: dict) -> dict:
    assert query == "hello"
    assert not need_filtering
    assert filtered_chunks is None
    assert retrieved_chunks == ["chunk for hello"]
    assert filtered_chunks_summary is None

    return {"final_answer": "final answer from chunks"}


def final_answer_generation_two_retrievals(query: str, need_filtering: bool, filtered_chunks: list[str], retrieved_chunks: list[str], filtered_chunks_summary: str, config: dict) -> dict:
    assert query == "hello"
    assert not need_filtering
    assert filtered_chunks is None
    assert retrieved_chunks == ["chunk for hello", "chunk for hello"]
    assert filtered_chunks_summary is None

    return {"final_answer": "final answer from chunks"}


def final_answer_generation_four_retrievals(query: str, need_filtering: bool, filtered_chunks: list[str], retrieved_chunks: list[str], filtered_chunks_summary: str, config: dict) -> dict:
    assert query == "hello"
    assert not need_filtering
    assert filtered_chunks is None
    assert retrieved_chunks == ["chunk for hello", "chunk for hello", "chunk for hello", "chunk for hello"]
    assert filtered_chunks_summary is None

    return {"final_answer": "final answer from chunks"}


def final_answer_generation_with_filtering(query: str, need_filtering: bool, filtered_chunks: list[str], retrieved_chunks: list[str], filtered_chunks_summary: str, config: dict) -> dict:
    assert query == "hello"
    assert need_filtering
    assert filtered_chunks == ["filtered chunk for hello"]
    assert retrieved_chunks == ["chunk for hello", "chunk for hello"]
    assert filtered_chunks_summary == "filtered chunks summary"

    return {"final_answer": "final answer from chunks"}


def test_wirl_one_cyclerunner_ok():
    FN_MAP = {
        "query_extender": query_extender,
        "retrieve_from_web": retrieve_from_web,
        "filter_chunks": filter_chunks,
        "final_answer_generation": final_answer_generation,
        "retrieve_results_check": retrieve_results_check,
    }
    result = run_workflow(WIRL_PATH, fn_map=FN_MAP, params={"query": "hello"})
    assert result.get("FinalAnswer.final_answer") == "final answer from chunks"
    assert result.get("RetrieveLoop.iteration_counter") == 0


def test_wirl_two_cycles_runner_ok():
    FN_MAP = {
        "query_extender": query_extender,
        "retrieve_from_web": retrieve_from_web,
        "filter_chunks": filter_chunks,
        "final_answer_generation": final_answer_generation_two_retrievals,
        "retrieve_results_check": retrieve_results_check_twice,
    }
    result = run_workflow(WIRL_PATH, fn_map=FN_MAP, params={"query": "hello"})
    assert result.get("FinalAnswer.final_answer") == "final answer from chunks"
    assert result.get("RetrieveLoop.iteration_counter") == 1


def test_wirl_max_iterations_runner_ok():
    FN_MAP = {
        "query_extender": query_extender,
        "retrieve_from_web": retrieve_from_web,
        "filter_chunks": filter_chunks,
        "final_answer_generation": final_answer_generation_four_retrievals,
        "retrieve_results_check": retrieve_results_check_false,
    }
    result = run_workflow(WIRL_PATH, fn_map=FN_MAP, params={"query": "hello"})
    assert result.get("FinalAnswer.final_answer") == "final answer from chunks"
    assert result.get("RetrieveLoop.iteration_counter") == 3


def test_wirl_two_cycles_runner_ok_with_filtering():
    FN_MAP = {
        "query_extender": query_extender,
        "retrieve_from_web": retrieve_from_web_with_filtering,
        "filter_chunks": filter_chunks,
        "final_answer_generation": final_answer_generation_with_filtering,
        "retrieve_results_check": retrieve_results_check_twice,
    }
    result = run_workflow(WIRL_PATH, fn_map=FN_MAP, params={"query": "hello"})
    assert result.get("FinalAnswer.final_answer") == "final answer from chunks"
    assert result.get("RetrieveLoop.iteration_counter") == 1
