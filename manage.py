import os
from app.web import create_app

app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "manage:app",
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 8000)),
        reload=True,
    )
