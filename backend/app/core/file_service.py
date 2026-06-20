"""File service for managing drawing and document paths."""

import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Optional

from src.core.config import settings


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to prevent path traversal and invalid characters."""
    filename = re.sub(r"[^\w\-\u4e00-\u9fff\u3000-\u303f\uff00-\uffef. ]", "", filename)
    filename = filename.strip(". ")
    if not filename:
        filename = "unnamed"
    return filename[:200]


def generate_unique_filename(original_filename: str) -> str:
    """Generate a unique filename with timestamp and short random suffix."""
    ext = Path(original_filename).suffix.lower()
    timestamp = datetime.utcnow().strftime("%Y%m%d")
    random_suffix = secrets.token_hex(4)
    safe_name = sanitize_filename(Path(original_filename).stem)
    return f"{safe_name}_{timestamp}_{random_suffix}{ext}"


def get_drawing_path(
    customer_name: str,
    part_name: str,
    filename: str,
    upload_date: Optional[datetime] = None,
) -> str:
    """Generate a secure drawing file path.

    Format: uploads/drawings/{customer_name}/{part_name}_{upload_date}.{ext}
    """
    if upload_date is None:
        upload_date = datetime.utcnow()

    safe_customer = sanitize_filename(customer_name)
    safe_part = sanitize_filename(part_name)
    unique_filename = generate_unique_filename(filename)
    date_str = upload_date.strftime("%Y%m%d")

    base_dir = settings.UPLOAD_DIR or "uploads"
    rel_path = os.path.join(
        base_dir,
        "drawings",
        safe_customer,
        f"{safe_part}_{date_str}_{unique_filename}",
    )
    return rel_path


def get_temp_drawing_path(filename: str) -> str:
    """Generate a path for temporarily stored drawings (before customer assignment)."""
    unique_filename = generate_unique_filename(filename)
    base_dir = settings.UPLOAD_DIR or "uploads"
    return os.path.join(base_dir, "drawings", "temp", unique_filename)


def migrate_drawing(
    source_path: str,
    customer_name: str,
    part_name: str,
    filename: str,
) -> str:
    """Migrate a drawing from temp path to final customer+part path.

    This is an atomic operation: on failure, the file stays at source.
    Returns the new final path.
    """
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"Source file not found: {source_path}")

    new_path = get_drawing_path(customer_name, part_name, filename)
    new_dir = os.path.dirname(new_path)
    os.makedirs(new_dir, exist_ok=True)

    os.rename(source_path, new_path)
    return new_path


def get_qrcode_path(qr_type: str, identifier: str) -> str:
    """Generate a path for QR code images.

    Args:
        qr_type: Type of QR code (material, machine, process_flow)
        identifier: Unique identifier (e.g., batch_001, machine_001)
    """
    safe_id = sanitize_filename(identifier)
    base_dir = settings.UPLOAD_DIR or "uploads"
    return os.path.join(base_dir, "qrcodes", qr_type, f"{safe_id}.png")


def ensure_upload_dir() -> None:
    """Ensure all upload directories exist."""
    base_dir = settings.UPLOAD_DIR or "uploads"
    dirs = [
        os.path.join(base_dir, "drawings"),
        os.path.join(base_dir, "drawings", "temp"),
        os.path.join(base_dir, "qrcodes", "material"),
        os.path.join(base_dir, "qrcodes", "machine"),
        os.path.join(base_dir, "qrcodes", "process_flow"),
    ]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
