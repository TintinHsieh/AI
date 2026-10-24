"""Start Coffee Chat Copilot:  python run.py   then open http://127.0.0.1:8000"""
import os
import webbrowser

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    if os.getenv("NO_BROWSER") != "1":
        webbrowser.open(f"http://127.0.0.1:{port}")
    uvicorn.run("app.main:app", host="127.0.0.1", port=port)
