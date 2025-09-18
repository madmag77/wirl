import os
import subprocess
import base64
import shutil
from io import BytesIO
from datetime import datetime, timedelta
import logging
from pydantic import BaseModel, Field
from PIL import Image as PILImage
from langchain_openai import ChatOpenAI

# Register HEIF opener with Pillow
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    logger.warning("pillow-heif not available, HEIC images will not be supported")

logger = logging.getLogger(__name__)


class Note(BaseModel):
    text: str = Field(description="Information extracted from the photo")


def get_photos(config: dict, obsidian_folder_path: str) -> dict:
    export_path = os.path.expanduser(config.get("export_path", "~/Exports"))
    
    # Clean the export folder before exporting to avoid duplicates
    if os.path.exists(export_path):
        shutil.rmtree(export_path)
    os.makedirs(export_path, exist_ok=True)
    
    from_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    subprocess.run([
        "osxphotos",
        "export",
        export_path,
        "--from-date",
        from_date,
        "--update",  # Use update flag to avoid interactive prompt
    ], check=True)
    file_paths = [
        os.path.join(export_path, f)
        for f in os.listdir(export_path)
        if f.lower().endswith((".png", ".jpg", ".jpeg", ".heic"))
    ]
    return {"file_paths": file_paths}


def read_photo(file_paths: list[str], initial_file_paths_to_process: list[str], config: dict) -> dict:
    file_paths_to_process = file_paths if file_paths else initial_file_paths_to_process
    if len(file_paths_to_process) == 0:
        return {"no_files_to_process": True}
    file_path = file_paths_to_process.pop(0)
    image = PILImage.open(file_path)
    return {
        "image": image,
        "file_path": file_path,
        "remaining_file_paths": file_paths_to_process,
    }


def extract_note(image: PILImage.Image, config: dict) -> dict:
    def encode_image(img: PILImage.Image) -> str:
        byte_arr = BytesIO()
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(byte_arr, format="JPEG")
        return base64.b64encode(byte_arr.getvalue()).decode("utf-8")

    llm_model = config.get("model")
    base_url = config.get("base_url")
    temperature = config.get("temperature", 0)
    vision_llm = ChatOpenAI(
        model=llm_model,
        base_url=base_url,
        temperature=temperature,
        api_key="sk",
    )
    structured_llm = vision_llm.with_structured_output(Note, method="json_mode")

    content = [
        {
            "type": "text",
            "text": "Extract any useful text, phone numbers, quotes, or warnings from this image. If nothing useful, return empty text.",
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encode_image(image)}"},
        },
    ]
    note = structured_llm.invoke([{"role": "user", "content": content}])
    return {"note": note.text}


def check_all_photos_processed(
    remaining_file_paths_to_process: list[str],
    note: str,
    no_files_to_process: bool,
    config: dict,
) -> dict:
    if no_files_to_process:
        return {"is_done": True, "notes": []}
    return {
        "is_done": len(remaining_file_paths_to_process) == 0,
        "notes": [note] if note else [],
    }


def save_notes(notes: list[str], obsidian_folder_path: str, config: dict) -> dict:
    date_str = datetime.now().strftime("%Y-%m-%d")
    os.makedirs(obsidian_folder_path, exist_ok=True)
    note_path = os.path.join(
        obsidian_folder_path, f"note_from_photos_{date_str}.md"
    )
    with open(note_path, "a", encoding="utf-8") as f:
        for n in notes:
            if n:
                f.write(f"- {n}\n")
    return {"notes_file_path": note_path}
