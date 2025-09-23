import os
import base64
import shutil
from io import BytesIO
from datetime import datetime, timedelta
import logging
from pydantic import BaseModel, Field
from PIL import Image as PILImage
from langchain_openai import ChatOpenAI
import osxphotos

# Register HEIF opener with Pillow
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    logger.warning("pillow-heif not available, HEIC images will not be supported")

logger = logging.getLogger(__name__)


def get_photos(config: dict, obsidian_folder_path: str) -> dict:
    export_path = os.path.expanduser(config.get("export_path", "~/Exports"))
    days_back = config.get("days_back", 1)

    # Clean the export folder before exporting to avoid duplicates
    if os.path.exists(export_path):
        shutil.rmtree(export_path)
    os.makedirs(export_path, exist_ok=True)
    
    from_date = datetime.now() - timedelta(days=days_back)
    
    photosdb = osxphotos.PhotosDB()
    photos = photosdb.photos(from_date=from_date)
    
    file_paths = []
    for photo in photos:
        if photo.ismissing or photo.intrash:
            continue
        
        try:
            exported = photo.export(export_path)
            if exported:
                file_paths.extend(exported)
        except Exception as e:
            logger.warning(f"Failed to export photo {photo.uuid}: {e}")
            continue
    
    logger.info(f"Exported {len(file_paths)} photos to {export_path}")
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

    content = [
        {
            "type": "text",
            "text": """
              Firstly, classify the phot into the one of the following classes: 
                1. Casual photo of people, buildings or nature.
                2. Photo of a product, food, or any other type of object close-up.
                3. Photo of a document, receipt, ticket, or any other type of document. 
                4. Screenshot of a text message, email, webpage, or any other type of screenshot.
                
                If the photo is of the class 1 return just a class of the photo without any other text.
                
                For the class 2, describe the object in details including all the texts on it. 
                For the class 3, describe the document and extract all the text from it trying to preserve formatting and layout. 
                For the class 4, describe the screenshot and extract all the text from it trying to preserve formatting and layout. 
            """,
        },
        {
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{encode_image(image)}"},
        },
    ]
    response = vision_llm.invoke([{"role": "user", "content": content}])
    return {"note": response.content}


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
        for i, n in enumerate(notes):
            if n:
                f.write(f"# Photo{i+1}\n")
                f.write(n)
                f.write("\n\n")
    return {"notes_file_path": note_path}
