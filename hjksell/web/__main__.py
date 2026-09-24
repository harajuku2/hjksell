"""Run the local HJKsell web development server."""

import os

import uvicorn


if __name__ == "__main__":
    # Bind to the local network so a phone on the same Wi-Fi can open the app.
    uvicorn.run(
        "hjksell.web.run:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", "8765")),
        reload=False,
    )
