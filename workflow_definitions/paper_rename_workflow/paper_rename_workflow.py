import os
import shutil
import base64
from io import BytesIO
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from pdf2image import convert_from_path
import logging
from workflow_definitions.paper_rename_workflow.prompts import get_vision_prompt
from PIL import Image as PILImage

logger = logging.getLogger(__name__)


class Book(BaseModel):
    book_name: str = Field(description="Book name")
    authors_names: list[str] = Field(
        description="array with authors names, empty if not found"
    )
    year: str = Field(description="the year book was published, `None` if not found")


def get_files(drafts_folder_path: str, config: dict) -> dict:
    return {
        "file_paths": [
            os.path.join(drafts_folder_path, f)
            for f in os.listdir(drafts_folder_path)
            if f.endswith(".pdf")
        ]
    }


def read_pdf_file(
    file_paths: list[str], initial_file_paths_to_process: list[str], config: dict
) -> dict:
    pages_to_read = config.get("pages_to_read")
    file_paths_to_process = file_paths if file_paths else initial_file_paths_to_process
    if len(file_paths_to_process) == 0:
        return {"no_files_to_process": True}
    file_path = file_paths_to_process.pop(0)
    # Render the first 2 pages of PDF as images using pdf2image
    try:
        # Convert first 2 pages to images at 200 DPI for good quality without being too large
        page_images = convert_from_path(
            file_path, dpi=200, first_page=1, last_page=pages_to_read
        )
        return {
            "pages": page_images,
            "file_path": file_path,
            "remaining_file_paths": file_paths_to_process,
        }
    except Exception as e:
        logger.error(f"Error rendering PDF pages as images: {str(e)}")
        raise e


def extract_metadata(pages: list[PILImage.Image], config: dict) -> dict:
    def encode_image_for_llm(image):
        byte_arr = BytesIO()
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        image.save(byte_arr, format="JPEG")
        img_str = base64.b64encode(byte_arr.getvalue()).decode("utf-8")
        return img_str

    llm_model = config.get("model")
    base_url = config.get("base_url")
    temperature = config.get("temperature")

    vision_llm = ChatOpenAI(
        model=llm_model,
        base_url=base_url,
        temperature=temperature,
        api_key="sk",
    )
    structured_vision_llm = vision_llm.with_structured_output(Book, method="json_mode")
    vision_book = None

    if not pages or len(pages) == 0:
        logger.error("No pages to read")
        raise Exception("No pages to read")

    content = [{"type": "text", "text": get_vision_prompt()}]

    # Add each page as an image
    for page in pages:
        content.append(
            {
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/jpeg;base64,{encode_image_for_llm(page)}"
                },
            }
        )

    vision_messages = [{"role": "user", "content": content}]
    vision_book = structured_vision_llm.invoke(vision_messages)

    return {
        "title": vision_book.book_name,
        "authors": vision_book.authors_names,
        "year": vision_book.year,
    }


def rename_file(
    file_path: str,
    title: str,
    authors: list[str],
    year: str,
    processed_folder_path: str,
    config: dict,
) -> dict:
    new_file_path = os.path.join(
        processed_folder_path, f"[{year}] {authors[0]} - {title}.pdf"
    )
    shutil.move(file_path, new_file_path)
    return {"new_file_path": new_file_path}


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
