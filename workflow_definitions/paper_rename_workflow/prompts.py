def get_vision_prompt() -> str:
    return """
    You are analyzing the title page and first pages of a book.
    
    Please extract the following information by looking at the provided images AND text:
    1. book_name - Find the complete title of the book
    2. authors_names - Identify all authors (as an array of names)
    3. year - The year the book was published (or "NONE" if not visible)
    4. book_category - Determine the book category (fiction, computer science, biology, etc.)

    Look for publishing information, title page formatting, and author credentials to improve accuracy.
    Pay special attention to the layout, font sizes, and positioning of text on the title page.

    Return ONLY a JSON with these fields. Use "NONE" for any missing information.
    """