import os
import uuid

ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}


def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_uploaded_file(file, upload_folder: str, request_id: str, doc_type: str) -> str:
    """Save an uploaded file and return its full path."""
    ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
    filename = f"{request_id}_{doc_type}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = os.path.join(upload_folder, filename)
    file.save(file_path)
    return file_path


def success(data: dict = None, **kwargs) -> dict:
    response = {"success": True}
    if data:
        response.update(data)
    response.update(kwargs)
    return response


def error(message: str, **kwargs) -> dict:
    response = {"success": False, "error": message}
    response.update(kwargs)
    return response
