"""Run the local HJKsell web development server."""

import uvicorn


if __name__ == "__main__":
    uvicorn.run("hjksell.web.run:app", host="127.0.0.1", port=8765, reload=False)
