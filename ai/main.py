import os
import tempfile

from fastapi import FastAPI, File, UploadFile
from fastapi.responses import JSONResponse

from ai.omr.pipeline import recognize

app = FastAPI(title="AI Music Mentor — OMR")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/recognize")
async def recognize_score(file: UploadFile = File(...)):
    suffix = os.path.splitext(file.filename or "upload.png")[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name

    try:
        result = recognize(tmp_path)
        return result.model_dump()
    except Exception as e:
        return JSONResponse(status_code=500, content={"error": str(e)})
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("ai.main:app", host="0.0.0.0", port=8000, reload=True)
