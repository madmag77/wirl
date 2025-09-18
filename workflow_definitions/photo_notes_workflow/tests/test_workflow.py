def run_workflow(path: str, fn_map: dict, params: dict) -> dict:
    photos = fn_map["get_photos"]({})["file_paths"]
    remaining = photos
    notes: list[str] = []
    while True:
        read = fn_map["read_photo"](remaining, photos, {})
        if read.get("no_files_to_process"):
            break
        note = fn_map["extract_note"](read["image"], {})["note"]
        check = fn_map["check_all_photos_processed"](read["remaining_file_paths"], note, False, {})
        notes.extend(check["notes"])
        remaining = read["remaining_file_paths"]
        if check["is_done"]:
            break
    save = fn_map["save_notes"](notes, params["obsidian_folder_path"], {})
    return {"SaveNotes.notes_file_path": save["notes_file_path"]}


def get_photos(config: dict) -> dict:
    return {"file_paths": ["a.jpg", "b.jpg"]}


def read_photo(file_paths: list[str], initial_file_paths_to_process: list[str], config: dict) -> dict:
    file_paths_to_process = file_paths if file_paths else initial_file_paths_to_process
    if len(file_paths_to_process) == 0:
        return {"no_files_to_process": True}
    return {
        "image": None,
        "file_path": file_paths_to_process[0],
        "remaining_file_paths": file_paths_to_process[1:],
    }


def extract_note(image, config: dict) -> dict:
    return {"note": "note"}


def check_all_photos_processed(remaining_file_paths_to_process: list[str], note: str, no_files_to_process: bool, config: dict) -> dict:
    if no_files_to_process:
        return {"is_done": True, "notes": []}
    return {
        "is_done": len(remaining_file_paths_to_process) == 0,
        "notes": [note],
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
        params={"obsidian_folder_path": "obs"},
    )
    assert result["SaveNotes.notes_file_path"] == "path.md"
