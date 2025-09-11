from PIL import Image
import easyocr
import numpy as np
import io

reader = easyocr.Reader(['en'],gpu=False)

def image_to_text(image_bytes: bytes):
    """
    Extract text from raw image bytes
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    np_image = np.array(image)
    text = reader.readtext(np_image, detail = 0)
    return ["\n".join(text).strip()]