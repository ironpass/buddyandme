import string

def format_text_response(text):
    """
    Formats the text response by removing emojis and special characters, 
    while keeping Thai and English characters.

    Args:
        text (str): The input text.

    Returns:
        str: The cleaned text.
    """
    # Define allowed ranges for Thai characters and common symbols
    thai_range = (0x0E00, 0x0E7F)  # Unicode range for Thai characters
    allowed_chars = string.ascii_letters + string.digits + string.punctuation + " "
    
    # Build a translation table for fast filtering
    translation_table = {
        ord(c): None
        for c in map(chr, range(0x110000))
        if c not in allowed_chars and not (thai_range[0] <= ord(c) <= thai_range[1])
    }

    # Translate to remove unwanted characters
    text = text.translate(translation_table)

    # Normalize spacing
    text = " ".join(text.split())
    
    return text