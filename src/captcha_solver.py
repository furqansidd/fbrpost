import os
import re
import base64
import requests
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

def sanitize_captcha_response(raw_text: str) -> str:
    """
    Cleans raw LLM response to extract strictly the alphanumeric captcha code.
    """
    if not raw_text:
        return ""
    # Strip markdown and common filler
    text = raw_text.replace("*", "").replace("`", "").strip()
    
    # Try to find standard 4 to 6 character alphanumeric code
    # e.g., "The text is: 8X2A." -> "8X2A"
    tokens = re.findall(r'[A-Za-z0-9]{3,8}', text)
    if tokens:
        # Prefer the token that is not a generic word like 'the', 'code', 'image'
        blacklist = {"THE", "CODE", "TEXT", "IMAGE", "IS", "HERE", "CAPTCHA"}
        filtered = [t for t in tokens if t.upper() not in blacklist]
        if filtered:
            return filtered[0].upper()
        return tokens[0].upper()
    
    # Fallback to pure alphanumeric filter
    cleaned = re.sub(r'[^A-Za-z0-9]', '', text)
    return cleaned.upper()

def solve_captcha_image(image_bytes: bytes, api_key: Optional[str] = None) -> str:
    """
    Submits captcha image to OpenRouter Gemini Vision API and returns the solved text.
    """
    key = api_key or os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise ValueError("OPENROUTER_API_KEY is not set.")

    b64_img = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:image/png;base64,{b64_img}"

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/fbr-posting-agent",
        "X-Title": "FBR IRIS Posting Agent",
    }
    
    prompt = "Read the exact characters in this CAPTCHA image. Return ONLY the 4 to 6 alphanumeric characters with no spaces, punctuation, or explanations."

    payload = {
        "model": "google/gemini-2.5-flash",
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": data_url}
                    }
                ]
            }
        ],
        "temperature": 0.0,
        "max_tokens": 16,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=20)
    if response.status_code != 200:
        # Fallback to gemini-3.5-flash
        payload["model"] = "google/gemini-3.5-flash"
        response = requests.post(url, headers=headers, json=payload, timeout=20)
        if response.status_code != 200:
            raise RuntimeError(f"OpenRouter API error {response.status_code}: {response.text}")

    res_json = response.json()
    raw_content = res_json["choices"][0]["message"]["content"]
    return sanitize_captcha_response(raw_content)
