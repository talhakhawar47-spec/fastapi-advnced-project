import httpx
import base64
import os

BASE_URL = "http://127.0.0.1:8001"

def test_ocr():
    print("Testing /ocr (file upload)...")
    # Using a dummy image file if exists, else skip
    if os.path.exists("test_image.jpg"):
        with open("test_image.jpg", "rb") as f:
            files = {"file": ("test_image.jpg", f, "image/jpeg")}
            # Need to login first or use a dummy user if auth is enabled
            # For now, just checking if it's reachable and structure
            pass
    print("Done (Manual test recommended via Swagger)")

def test_scan_ocr():
    print("Testing /scan-ocr (JSON payload)...")
    # Base64 encoded dummy image (1x1 white pixel)
    pixel = base64.b64encode(b"\xff\xd8\xff\xdb\x00\x43\x00\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\x0d\x0c\x0b\x0b\x0c\x19\x12\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c\x20\x24\x2e\x27\x20\x22\x2c\x23\x1c\x1c\x28\x37\x29\x2c\x30\x31\x34\x34\x34\x1f\x27\x39\x3d\x38\x32\x3c\x2e\x33\x34\x32\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x14\x00\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xc4\x00\x14\x10\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xda\x00\x08\x01\x01\x00\x00\x3f\x00\x37\xff\xd9").decode()
    payload = {
        "image_data": f"data:image/jpeg;base64,{pixel}",
        "filename": "test-pixel.jpg"
    }
    # This will fail with 401 if auth is working correctly, which is a good sign
    try:
        r = httpx.post(f"{BASE_URL}/scan-ocr", json=payload)
        print(f"Status: {r.status_code}")
        print(f"Response: {r.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_scan_ocr()
