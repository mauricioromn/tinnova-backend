import hashlib
from PIL import Image
import imagehash
from io import BytesIO

def sha256_bytes(data: bytes) -> str:
    """Return hex sha256 of raw bytes."""
    return hashlib.sha256(data).hexdigest()

def phash_from_bytes(data: bytes) -> str:
    """Return perceptual hash (hex) from image bytes."""
    with Image.open(BytesIO(data)) as im:
        return str(imagehash.phash(im))

def hamming(hex_a: str, hex_b: str) -> int:
    """Hamming distance between two hex strings of same length."""
    return bin(int(hex_a, 16) ^ int(hex_b, 16)).count("1")