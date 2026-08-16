from fastapi.responses import JSONResponse

def ok(data=None, meta=None, status_code=200):
    body = {"success": True, "data": data if data is not None else {}}
    if meta:
        body["meta"] = meta
    return JSONResponse(status_code=status_code, content=body)

def fail(code: str, message: str, details=None, status_code=400):
    return JSONResponse(
        status_code=status_code,
        content={"success": False, "error": {"code": code, "message": message, "details": details or {}}},
    )