import os
import base64
from io import BytesIO
from datetime import datetime
import logging
from pydantic import BaseModel, Field
from PIL import Image as PILImage
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)

# Register HEIF opener with Pillow
try:
    from pillow_heif import register_heif_opener
    register_heif_opener()
except ImportError:
    logger.warning("pillow-heif not available, HEIC images will not be supported")

logger = logging.getLogger(__name__)


def get_photos(config: dict, obsidian_folder_path: str) -> dict:
    export_path = os.path.expanduser(config.get("export_path", "~/Exports"))
    
    # Ensure export directory exists
    os.makedirs(export_path, exist_ok=True)
    
    # Read all image files from the export directory
    file_paths = []
    supported_extensions = {'.jpg', '.jpeg', '.png', '.heic', '.heif', '.tiff', '.tif', '.bmp', '.gif'}
    
    try:
        for filename in os.listdir(export_path):
            file_path = os.path.join(export_path, filename)
            if os.path.isfile(file_path):
                _, ext = os.path.splitext(filename.lower())
                if ext in supported_extensions:
                    file_paths.append(file_path)
        
        file_paths.sort()  # Sort for consistent processing order
        logger.info(f"Found {len(file_paths)} image files in {export_path}")
        
    except Exception as e:
        logger.error(f"Error reading files from {export_path}: {e}")
        file_paths = []
    
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

    llm_model = config.get("model", "gemma3:12b")
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
                
                For the class 1, describe the photo.
                For the class 2, describe the object in details including all the texts on it. 
                For the class 3, describe the document and extract all the text from it trying to preserve formatting and layout. 
                For the class 4, describe the important information from the screenshot and extract all the text from it trying to preserve formatting and layout. Don't describe colors or background, just the important information.  
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
