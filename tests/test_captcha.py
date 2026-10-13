import os
import pytest
from src.captcha_solver import solve_captcha_image, sanitize_captcha_response

def test_sanitize_captcha_response():
    assert sanitize_captcha_response("7K9M") == "7K9M"
    assert sanitize_captcha_response("  7k9m  \n") == "7K9M"
    assert sanitize_captcha_response("The text is: 8X2A.") == "8X2A"
    assert sanitize_captcha_response("**AB12**") == "AB12"

def test_captcha_solver_interface_mock(monkeypatch):
    # Test that solver handles requests response properly
    class MockResponse:
        status_code = 200
        def json(self):
            return {
                "choices": [
                    {
                        "message": {
                            "content": "4W7Z"
                        }
                    }
                ]
            }

    dummy_png = (
        b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01'
        b'\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff'
        b'?\x00\x05\xfe\x02\xfe\r\xef5\xc8\x00\x00\x00\x00IEND\xaeB`\x82'
    )

    import requests
    monkeypatch.setattr(requests, "post", lambda *args, **kwargs: MockResponse())
    
    result = solve_captcha_image(dummy_png, api_key="dummy_key")
    assert result == "4W7Z"
