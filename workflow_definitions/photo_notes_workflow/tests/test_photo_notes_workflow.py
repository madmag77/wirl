from wirl_pregel_runner import run_workflow


def get_photos(config: dict, obsidian_folder_path: str) -> dict:
    return {"file_paths": ["a.jpg", "b.jpg"]}


def read_photo(file_paths: list[str] | None, initial_file_paths_to_process: list[str], config: dict) -> dict:
    file_paths_to_process = file_paths or initial_file_paths_to_process
    if not file_paths_to_process:
        return {"no_files_to_process": True}
    file_path = file_paths_to_process.pop(0)
    return {
        "image": 'image',
        "file_path": file_path,
        "remaining_file_paths": file_paths_to_process,
    }


def extract_note(image, config: dict) -> dict:
    return {"note": "note"}


def check_all_photos_processed(
    remaining_file_paths_to_process: list[str] | None, 
    note: str | None, 
    no_files_to_process: bool | None, 
    config: dict
) -> dict:
    if no_files_to_process:
        return {"is_done": True, "notes": []}
    remaining = remaining_file_paths_to_process or []
    return {
        "is_done": len(remaining) == 0,
        "notes": [note] if note else [],
    }


def save_notes(notes: list[str], obsidian_folder_path: str, config: dict) -> dict:
    return {"notes_file_path": "path.md"}


FN_MAP = {
    "get_photos": get_photos,
    "read_photo": read_photo,
    "extract_note": extract_note,
    "check_all_photos_processed": check_all_photos_processed,
    "save_notes": save_notes,
}


def test_photo_notes_e2e():
    result = run_workflow(
        "workflow_definitions/photo_notes_workflow/photo_notes_workflow.wirl",
        fn_map=FN_MAP,
        params={
            "obsidian_folder_path": "obs",
        },
    )
    print(result)
    assert result["SaveNotes.notes_file_path"] == "path.md"
