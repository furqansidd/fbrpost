import sys
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    print(f"\n=======================================================")
    print(f"[*] FBR IRIS 2.0 Auto-Posting Suite is Launching")
    print(f"[*] Dashboard URL: http://localhost:{port}")
    print(f"[*] Safe Draft Mode: Active (Submit & PIN are locked)")
    print(f"=======================================================\n")
    uvicorn.run("src.dashboard.app:app", host="127.0.0.1", port=port, reload=False)
