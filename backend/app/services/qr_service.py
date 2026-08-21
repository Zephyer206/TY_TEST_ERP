"""QR Code generation and lookup service."""

import base64
import io
from datetime import datetime
from enum import Enum
from typing import Optional, Union

from PIL import Image

from app.config import settings


class QRCodePrefix(str, Enum):
    """QR code prefix types for different entities."""

    MATERIAL = "MAT"  # 原料批次
    MACHINE = "MCN"  # 机台
    PROCESS_FLOW = "PFC"  # 工艺流转单
    PART = "PRT"  # 零件
    TOOLING = "TLG"  # 模具工装
    PACKAGE = "PKG"  # 包装
    COATING = "COT"  # 喷涂


def generate_qr_content(prefix: QRCodePrefix, entity_id: int, **extra_data) -> str:
    """Generate QR code content string.

    Args:
        prefix: The QR code prefix type
        entity_id: The entity ID
        **extra_data: Additional data to include

    Returns:
        JSON-like string format: {prefix}:{id}:{timestamp}:{extra}
    """
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    extras = ":".join(f"{k}={v}" for k, v in extra_data.items()) if extra_data else ""
    base = f"{prefix.value}:{entity_id}:{timestamp}"
    return f"{base}:{extras}" if extras else base


def generate_material_qr(batch_id: int, batch_no: str) -> str:
    """Generate QR content for material batch."""
    return generate_qr_content(QRCodePrefix.MATERIAL, batch_id, batch_no=batch_no)


def generate_material_batch_qr(batch_id: int) -> str:
    """Generate stable QR content for material batch (storeable in DB).

    Format: MAT:{batch_id}:{YYYYMMDD}
    Content is stable — same batch_id always produces same content.
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")
    return f"MAT:{batch_id}:{date_str}"


def generate_material_batch_qr_base64(batch_id: int, size: int = 300) -> str:
    """Generate QR image as base64 for material batch label printing.

    Returns:
        data:image/png;base64,{base64}
    """
    content = generate_material_batch_qr(batch_id)
    return generate_qr_base64(content, size=size)


def generate_machine_qr(machine_id: int, machine_no: str) -> str:
    """Generate QR content for machine."""
    return generate_qr_content(QRCodePrefix.MACHINE, machine_id, machine_no=machine_no)


def generate_process_flow_qr(card_id: int, card_no: str) -> str:
    """Generate QR content for process flow card."""
    return generate_qr_content(QRCodePrefix.PROCESS_FLOW, card_id, card_no=card_no)


def generate_part_qr(part_id: int, customer_part_no: str) -> str:
    """Generate QR content for part."""
    return generate_qr_content(QRCodePrefix.PART, part_id, customer_part_no=customer_part_no)


def generate_tooling_qr(tooling_id: int, tooling_number: str) -> str:
    """Generate QR content for tooling."""
    return generate_qr_content(QRCodePrefix.TOOLING, tooling_id, tooling_number=tooling_number)


def generate_package_qr(package_id: int, package_no: str) -> str:
    """Generate QR content for package."""
    return generate_qr_content(QRCodePrefix.PACKAGE, package_id, package_no=package_no)


def generate_coating_qr(record_id: int, record_no: str) -> str:
    """Generate QR content for coating record."""
    return generate_qr_content(QRCodePrefix.COATING, record_id, record_no=record_no)


def parse_qr_content(content: str) -> Optional[dict]:
    """Parse QR code content.

    Args:
        content: The QR code content string

    Returns:
        Parsed data dict with prefix, entity_id, timestamp, and extra data
    """
    parts = content.split(":")
    if len(parts) < 3:
        return None

    prefix = parts[0]
    entity_id = parts[1]
    timestamp = parts[2]

    extra = {}
    for part in parts[3:]:
        if "=" in part:
            k, v = part.split("=", 1)
            extra[k] = v

    return {
        "prefix": prefix,
        "entity_id": int(entity_id) if entity_id.isdigit() else entity_id,
        "timestamp": timestamp,
        "extra": extra,
    }


def get_prefix_type(prefix: str) -> Optional[QRCodePrefix]:
    """Get QRCodePrefix enum from string prefix."""
    try:
        return QRCodePrefix(prefix.upper())
    except ValueError:
        return None


def generate_qr_image(
    content: str,
    size: int = 300,
    border: int = 2,
    fill_color: str = "black",
    back_color: str = "white",
) -> bytes:
    """Generate QR code image as bytes.

    Args:
        content: The content to encode in the QR code
        size: The size of the QR code image in pixels
        border: The border size (modules)
        fill_color: The foreground color
        back_color: The background color

    Returns:
        PNG image bytes
    """
    import qrcode

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=border,
    )
    qr.add_data(content)
    qr.make(fit=True)

    img = qr.make_image(fill_color=fill_color, back_color=back_color)
    img = img.resize((size, size), Image.Resampling.LANCZOS)

    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer.getvalue()


def generate_qr_base64(
    content: str,
    size: int = 300,
    border: int = 2,
    fill_color: str = "black",
    back_color: str = "white",
) -> str:
    """Generate QR code as base64 encoded string.

    Returns:
        Base64 string with data URI prefix: data:image/png;base64,{base64}
    """
    img_bytes = generate_qr_image(content, size, border, fill_color, back_color)
    base64_str = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:image/png;base64,{base64_str}"


async def upload_qr_to_cos(
    content: str,
    filename: str,
    size: int = 300,
) -> Optional[str]:
    """Upload QR code image to cloud storage (COS/S3).

    Args:
        content: The QR code content
        filename: The filename for the uploaded image
        size: The QR code size

    Returns:
        The URL of the uploaded image, or None if upload fails
    """
    img_bytes = generate_qr_image(content, size)

    # Check if COS is configured
    if not settings.COS_SECRET_ID or not settings.COS_BUCKET:
        # Return local storage path if COS not configured
        return await _save_qr_locally(img_bytes, filename)

    try:
        return await _upload_to_cos(img_bytes, filename)
    except Exception as e:
        # Fallback to local storage
        print(f"COS upload failed: {e}, falling back to local storage")
        return await _save_qr_locally(img_bytes, filename)


async def _upload_to_cos(img_bytes: bytes, filename: str) -> str:
    """Upload image to Tencent COS or compatible S3 storage."""
    try:
        # Try Tencent COS first
        from qcloud_cos import CosConfig, CosS3Client

        config = CosConfig(
            Region=settings.COS_REGION,
            SecretId=settings.COS_SECRET_ID,
            SecretKey=settings.COS_SECRET_KEY,
            Endpoint=settings.COS_ENDPOINT or None,
        )
        client = CosS3Client(config)

        bucket = settings.COS_BUCKET
        key = f"qrcodes/{filename}"

        client.put_object(
            Bucket=bucket,
            Body=img_bytes,
            Key=key,
            ContentType="image/png",
        )

        # Construct URL
        if settings.COS_ENDPOINT:
            url = f"https://{bucket}.cos.{settings.COS_REGION}.myqcloud.com/{key}"
        else:
            url = f"https://{bucket}.cos.{settings.COS_REGION}.myqcloud.com/{key}"

        return url
    except ImportError:
        # Try阿里云OSS
        try:
            import oss2

            auth = oss2.Auth(settings.COS_SECRET_ID, settings.COS_SECRET_KEY)
            bucket = oss2.Bucket(
                auth,
                settings.COS_ENDPOINT or f"https://oss-{settings.COS_REGION}.aliyuncs.com",
                settings.COS_BUCKET,
            )

            key = f"qrcodes/{filename}"
            bucket.put_object(key, img_bytes)

            return f"https://{settings.COS_BUCKET}.oss-{settings.COS_REGION}.aliyuncs.com/{key}"
        except ImportError:
            raise ImportError(
                "Neither qcloud_cos nor oss2 is installed. "
                "Please install one of them for cloud storage."
            )


async def _save_qr_locally(img_bytes: bytes, filename: str) -> str:
    """Save QR code image to local storage."""
    import os
    import uuid

    upload_dir = settings.UPLOAD_DIR
    qr_dir = os.path.join(upload_dir, "qrcodes")

    # Create directory if not exists
    os.makedirs(qr_dir, exist_ok=True)

    # Generate unique filename
    if not filename.endswith(".png"):
        filename = f"{filename}.png"

    filepath = os.path.join(qr_dir, filename)

    with open(filepath, "wb") as f:
        f.write(img_bytes)

    # Return relative URL
    return f"/static/uploads/qrcodes/{filename}"


class QRLookupResult:
    """Result of QR code lookup."""

    def __init__(
        self,
        found: bool,
        prefix: Optional[str] = None,
        entity_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        entity_data: Optional[dict] = None,
        error: Optional[str] = None,
    ):
        self.found = found
        self.prefix = prefix
        self.entity_id = entity_id
        self.entity_type = entity_type
        self.entity_data = entity_data
        self.error = error

    def to_dict(self) -> dict:
        return {
            "found": self.found,
            "prefix": self.prefix,
            "entity_id": self.entity_id,
            "entity_type": self.entity_type,
            "entity_data": self.entity_data,
            "error": self.error,
        }
