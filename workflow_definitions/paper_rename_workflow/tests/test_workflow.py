from wirl_pregel_runner import run_workflow


def get_files(drafts_folder_path: str, config: dict) -> dict:
    return {"file_paths": ["tests/test_files/test.pdf", "tests/test_files/test2.pdf"]}


def read_pdf_file(
    file_paths: list[str], initial_file_paths_to_process: list[str], config: dict
) -> dict:
    file_paths_to_process = file_paths if file_paths else initial_file_paths_to_process
    if len(file_paths_to_process) == 0:
        return {"no_files_to_process": True}
    return {
        "pages": [],
        "file_path": file_paths_to_process[0],
        "remaining_file_paths": file_paths_to_process[1:],
    }


def extract_metadata(pages: list, config: dict) -> dict:
    return {"title": "test", "authors": ["test"], "year": "2025"}


def rename_file(
    file_path: str,
    title: str,
    authors: list[str],
    year: str,
    processed_folder_path: str,
    config: dict,
) -> dict:
    return {"new_file_path": "new_file_path"}


def check_all_files_processed(
    remaining_file_paths_to_process: list[str],
    processed_file: str,
    no_files_to_process: bool,
    config: dict,
) -> dict:
    if no_files_to_process:
        return {"is_done": True, "processed_files": []}
    return {
        "is_done": len(remaining_file_paths_to_process) == 0,
        "processed_files": [processed_file],
    }


def return_processed_files(processed_files: list[str], config: dict) -> dict:
    return {"processed_files": processed_files}


FN_MAP = {
    "get_files": get_files,
    "read_pdf_file": read_pdf_file,
    "extract_metadata": extract_metadata,
    "rename_file": rename_file,
    "check_all_files_processed": check_all_files_processed,
    "return_processed_files": return_processed_files,
}


def test_paper_rename_e2e():
    drafts = "drafts"
    processed = "processed"

    result = run_workflow(
        "workflow_definitions/paper_rename_workflow/paper_rename_workflow.wirl",
        fn_map=FN_MAP,
        params={
            "drafts_folder_path": drafts,
            "processed_folder_path": processed,
        },
    )
    assert result["ReturnProcessedFiles.processed_files"] == [
        "new_file_path",
        "new_file_path",
    ]
