import base64
import json
import os
import time
import httpx

DEFAULT_OCR_MIME_TYPE = "image/jpeg"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_BASE_URL = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_OCR_MODEL = os.getenv(
    "GROQ_OCR_MODEL",
    "meta-llama/llama-4-scout-17b-16e-instruct",
)
GROQ_TIMEOUT_SECONDS = float(os.getenv("GROQ_TIMEOUT_SECONDS", "45"))


def decode_image_payload(image_data: str) -> tuple[bytes, str]:
    """
    Decodes a base64 image payload which might start with a 'data:image/...;base64,' prefix.
    Returns (image_bytes, mime_type).
    """
    if "," in image_data:
        header, encoded = image_data.split(",", 1)
        mime_type = header.split(";")[0].split(":")[1]
        image_bytes = base64.b64decode(encoded)
    else:
        # Fallback if raw base64 is provided
        image_bytes = base64.b64decode(image_data)
        mime_type = DEFAULT_OCR_MIME_TYPE
    return image_bytes, mime_type



def _build_prompt(filename: str) -> str:
    return (
        "You are an OCR engine. Extract all readable text from the image. "
        "Preserve line breaks and paragraph spacing. If handwriting is present, "
        "do your best to transcribe it. Respond ONLY with JSON using this schema: "
        "{\"status\":\"ok\",\"document\":{\"filename\":\"...\","
        "\"handwritten\":true/false,\"language\":\"...\","
        "\"text\":\"...\",\"notes\":\"...\"}}."
        f" The filename is {json.dumps(filename)}."
    )


def _build_payload(image_bytes: bytes, mime_type: str, filename: str) -> dict:
    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{mime_type};base64,{encoded}"

    return {
        "model": GROQ_OCR_MODEL,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _build_prompt(filename)},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
    }


async def perform_ocr(image_bytes: bytes, mime_type: str, filename: str) -> dict:
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY is required to perform OCR.")

    payload = _build_payload(image_bytes, mime_type, filename)
    headers = {"Authorization": f"Bearer {GROQ_API_KEY}"}

    start_time = time.monotonic()
    async with httpx.AsyncClient(timeout=GROQ_TIMEOUT_SECONDS) as client:
        response = await client.post(
            f"{GROQ_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )
    elapsed_ms = int((time.monotonic() - start_time) * 1000)

    if response.status_code != 200:
        print(f"--- GROQ API ERROR ({response.status_code}) ---")
        print(response.text)
        response.raise_for_status()
    data = response.json()
    content_str = data["choices"][0]["message"]["content"]
    if isinstance(content_str, str):
        cleaned = content_str.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()
        content_str = cleaned
    
    try:
        content = json.loads(content_str)
        # Check if it has the structure we expect (status and document)
        if not isinstance(content, dict) or "document" not in content:
             # Try to wrap it if it's just the document part
             if isinstance(content, dict) and "text" in content:
                 content = {"status": "ok", "document": content}
             else:
                 raise ValueError("Unexpected JSON structure")
    except (json.JSONDecodeError, TypeError, ValueError):
        # Structured fallback to match OCRResult schema
        content = {
            "status": "error",
            "document": {
                "filename": filename,
                "handwritten": False,
                "language": "unknown",
                "text": content_str if isinstance(content_str, str) else "No text extracted",
                "notes": "Warning: Groq did not return valid JSON. This is raw text fallback."
            }
        }

    return {
        "status": content.get("status", "ok"),
        "model": data.get("model", GROQ_OCR_MODEL),
        "elapsed_ms": elapsed_ms,
        "usage": data.get("usage", {}),
        "content": content,
        "raw_content": content_str,
        "parse_error": None if content.get("status") != "error" else content.get("document", {}).get("notes")
    }