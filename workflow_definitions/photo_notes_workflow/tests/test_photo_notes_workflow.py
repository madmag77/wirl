import json
from wirl_pregel_runner import run_workflow
from langgraph.checkpoint.memory import MemorySaver


def get_photos(config: dict, obsidian_folder_path: str) -> dict:
    return {"file_paths": ["a.jpg", "b.jpg"]}


def read_photo(
    file_paths: list[str] | None, initial_file_paths_to_process: list[str], config: dict
) -> dict:
    file_paths_to_process = file_paths or initial_file_paths_to_process
    if not file_paths_to_process:
        return {"no_files_to_process": True}
    file_path = file_paths_to_process.pop(0)
    return {
        "image": "image",
        "file_path": file_path,
        "remaining_file_paths": file_paths_to_process,
    }


def extract_note(image, config: dict) -> dict:
    return {"note": f"note from {image}"}


def check_all_photos_processed(
    remaining_file_paths_to_process: list[str] | None,
    note: str | None,
    no_files_to_process: bool | None,
    config: dict,
) -> dict:
    if no_files_to_process:
        return {"is_done": True, "notes": []}
    remaining = remaining_file_paths_to_process or []
    return {
        "is_done": len(remaining) == 0,
        "notes": [note] if note else [],
    }


def agree_with_user(notes: list[str], config: dict) -> dict:
    # Mock HITL function - in real workflow this would send email
    # The return value will be overridden by resume parameter
    return {"comments_from_user": "placeholder"}


def apply_user_comments(
    notes: list[str], comments_from_user: str, config: dict
) -> dict:
    # Mock function that applies user comments to notes
    return {
        "notes_to_save": f"Applied comments: {comments_from_user} to notes: {notes}"
    }


def save_notes(
    notes: str | None,
    no_files_found: bool | None,
    obsidian_folder_path: str,
    config: dict,
) -> dict:
    if no_files_found or not notes:
        return {"notes_file_path": "no notes to save"}
    return {"notes_file_path": "path.md"}


FN_MAP = {
    "get_photos": get_photos,
    "read_photo": read_photo,
    "extract_note": extract_note,
    "check_all_photos_processed": check_all_photos_processed,
    "agree_with_user": agree_with_user,
    "apply_user_comments": apply_user_comments,
    "save_notes": save_notes,
}


def test_photo_notes_e2e():
    """Test the full workflow with HITL when photos are found."""
    # Create a memory checkpointer for HITL
    checkpointer = MemorySaver()
    thread_id = "test-thread-123"

    # First run - will pause at HITL (AgreeWithUser node)
    result_first = run_workflow(
        "workflow_definitions/photo_notes_workflow/photo_notes_workflow.wirl",
        fn_map=FN_MAP,
        params={
            "obsidian_folder_path": "obs",
        },
        thread_id=thread_id,
        checkpointer=checkpointer,
    )

    print("First run result:", result_first)
    # At this point, workflow has paused at HITL
    assert "__interrupt__" in result_first, "Workflow should pause at HITL node"

    # Second run - resume with user input
    # The user response needs to be JSON-encoded as the runner expects a JSON string
    user_response = {"user_response": "These notes look great, please save them!"}
    result_final = run_workflow(
        "workflow_definitions/photo_notes_workflow/photo_notes_workflow.wirl",
        fn_map=FN_MAP,
        params={
            "obsidian_folder_path": "obs",
        },
        thread_id=thread_id,
        resume=json.dumps(user_response),
        checkpointer=checkpointer,
    )

    print("Final result:", result_final)
    assert result_final["SaveNotes.notes_file_path"] == "path.md"


def test_photo_notes_no_files_shortcut():
    """Test the shortcut case where no photos are found."""
    # Custom function map for this test that returns no files
    fn_map_no_files = FN_MAP.copy()
    fn_map_no_files["get_photos"] = lambda config, obsidian_folder_path: {
        "no_files_found": True
    }

    result = run_workflow(
        "workflow_definitions/photo_notes_workflow/photo_notes_workflow.wirl",
        fn_map=fn_map_no_files,
        params={
            "obsidian_folder_path": "obs",
        },
    )

    print("No files result:", result)
    # When no files are found, workflow should skip HITL and go directly to SaveNotes
    assert result["SaveNotes.notes_file_path"] == "no notes to save"
    assert (
        "__interrupt__" not in result
    ), "Workflow should not pause when no files found"
