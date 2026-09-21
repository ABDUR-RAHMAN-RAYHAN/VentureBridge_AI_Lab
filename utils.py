import os
import secrets
from flask import current_app


def allowed_file(filename, allowed_exts):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in allowed_exts


def guess_image_type(stream_bytes):
    """
    Sniff real image type from magic bytes (defends against renamed-extension
    attacks). Implemented by hand instead of the stdlib `imghdr` module, which
    was removed in Python 3.13.
    """
    if stream_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if stream_bytes.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


def save_upload(file_storage, subfolder, allowed_exts):
    """
    Validates a werkzeug FileStorage by extension + size + real file-content
    sniffing, saves it under a randomized filename inside
    UPLOAD_FOLDER/subfolder. Returns the stored filename (relative) or
    raises ValueError on invalid input.
    """
    if not file_storage or file_storage.filename == "":
        raise ValueError("No file provided.")

    filename = file_storage.filename
    if not allowed_file(filename, allowed_exts):
        raise ValueError("File type not allowed.")

    data = file_storage.read()
    if len(data) == 0:
        raise ValueError("Empty file.")
    if len(data) > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ValueError("File too large.")

    ext = filename.rsplit(".", 1)[1].lower()
    if ext in {"png", "jpg", "jpeg"}:
        real = guess_image_type(data)
        if real not in ("jpeg", "png"):
            raise ValueError("File content does not match an allowed image type.")

    random_name = f"{secrets.token_hex(16)}.{ext}"
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, random_name)
    with open(path, "wb") as f:
        f.write(data)
    return f"{subfolder}/{random_name}"
