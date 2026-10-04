import os
import base64
import binascii
import secrets
from datetime import datetime
from flask import current_app, request
from flask_login import current_user
from werkzeug.datastructures import FileStorage
from extensions import db
from models import AuditLog


def is_upload(candidate):
    """
    True only when a form field holds a *freshly uploaded* file.

    WTForms file fields keep whatever they were pre-populated with when the
    form is built from an existing record (e.g. ProfileForm(obj=profile)
    puts the stored filename string into form.photo.data). On submit without
    a new file, that string is still sitting there and is truthy, which used
    to reach save_upload() and blow up with
    "'str' object has no attribute 'filename'". Always gate uploads on this
    helper instead of on plain truthiness.
    """
    return isinstance(candidate, FileStorage) and bool(candidate.filename)


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
    Validates a werkzeug FileStorage by extension + size, saves it under a
    randomized filename inside UPLOAD_FOLDER/subfolder. Returns the stored
    filename (relative) or raises ValueError on invalid input.
    """
    if not is_upload(file_storage):
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
    # For images, sniff the real bytes; for pdf just check the magic header.
    if ext in {"png", "jpg", "jpeg"}:
        real = guess_image_type(data)
        if real not in ("jpeg", "png"):
            raise ValueError("File content does not match an allowed image type.")
    elif ext == "pdf":
        if not data[:4] == b"%PDF":
            raise ValueError("File content does not match a PDF.")

    random_name = f"{secrets.token_hex(16)}.{ext}"
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, random_name)
    with open(path, "wb") as f:
        f.write(data)
    return f"{subfolder}/{random_name}"


def save_base64_image(data_url, subfolder):
    """
    Saves a webcam-captured image sent as a data URL (data:image/png;base64,....)
    Used for the live NID verification photos. Returns stored relative filename.
    """
    if not data_url or "," not in data_url:
        raise ValueError("Invalid image data.")
    header, b64data = data_url.split(",", 1)
    if "image/png" not in header and "image/jpeg" not in header:
        raise ValueError("Unsupported image format.")
    try:
        raw = base64.b64decode(b64data, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("Corrupted image data.")

    if len(raw) == 0 or len(raw) > current_app.config["MAX_CONTENT_LENGTH"]:
        raise ValueError("Invalid image size.")

    kind = guess_image_type(raw)
    if kind not in ("png", "jpeg"):
        raise ValueError("Captured image failed validation.")

    random_name = f"{secrets.token_hex(16)}.{kind if kind != 'jpeg' else 'jpg'}"
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, random_name)
    with open(path, "wb") as f:
        f.write(raw)
    return f"{subfolder}/{random_name}"


def log_action(action, details="", user_id=None):
    """Writes an entry to the audit log. Never raises to the caller."""
    try:
        uid = user_id
        if uid is None and current_user and current_user.is_authenticated:
            uid = current_user.id
        entry = AuditLog(
            user_id=uid,
            action=action,
            details=details,
            ip_address=request.remote_addr if request else None,
            created_at=datetime.utcnow(),
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        db.session.rollback()


def make_reference_no(request_id):
    return f"VB-AGR-{request_id:06d}-{secrets.token_hex(2).upper()}"
