import pytesseract
import re
from PIL import Image

def extract_data(file):
    image = Image.open(file)
    text = pytesseract.image_to_string(image, lang='rus+eng')

    snils = re.search(r'\d{3}[-\s]?\d{3}[-\s]?\d{3}[-\s]?\d{2}', text)
    inn = re.search(r'\b\d{10,12}\b', text)
    passport = re.search(r'\b\d{2}\s?\d{2}\s?\d{6}\b', text)

    return {
        "snils": snils.group(0) if snils else "",
        "inn": inn.group(0) if inn else "",
        "passport": passport.group(0) if passport else ""
    }
