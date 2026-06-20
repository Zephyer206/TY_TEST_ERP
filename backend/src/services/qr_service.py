"""
QR Code generation and management service.

Provides QR code generation with customizable content for:
- Material batches (MAT-{batch_id})
- Machine codes (MCN-{machine_id})
- Process flow cards (PFC-{card_id})
- Parts (PRT-{part_id})
- Packaging records (PKG-{record_id})
"""

import base64
import io
from datetime import datetime
from enum import Enum
from typing import Optional

try:
    import qrcode
    from PIL import Image, ImageDraw, ImageFont
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

from app.core.config import settings


class QRType(str, Enum):
    """QR code types based on prefix."""

    MATERIAL = "MAT"  # 原料批次
    MACHINE = "MCN"  # 机台
    PROCESS_FLOW = "PFC"  # 工艺流转单
    PART = "PRT"  # 零件
    PACKAGING = "PKG"  # 包装记录
    COATING = "COA"  # 喷涂记录


# QR Code content structure
QR_CONTENT_TEMPLATE = {
    QRType.MATERIAL: "https://{domain}/qr/material/{id}",
    QRType.MACHINE: "https://{domain}/qr/machine/{id}",
    QRType.PROCESS_FLOW: "https://{domain}/qr/process-flow/{id}",
    QRType.PART: "https://{domain}/qr/part/{id}",
    QRType.PACKAGING: "https://{domain}/qr/packaging/{id}",
    QRType.COATING: "https://{domain}/qr/coating/{id}",
}


def get_qr_type(code: str) -> Optional[QRType]:
    """Parse QR code and determine its type."""
    if not code:
        return None

    prefix = code.split("-")[0] if "-" in code else code[:3]

    type_map = {
        "MAT": QRType.MATERIAL,
        "MCN": QRType.MACHINE,
        "PFC": QRType.PROCESS_FLOW,
        "PRT": QRType.PART,
        "PKG": QRType.PACKAGING,
        "COA": QRType.COATING,
    }

    return type_map.get(prefix.upper())


def parse_qr_code(code: str) -> Optional[dict]:
    """
    Parse QR code string and extract type and ID.

    Format: {PREFIX}-{ID}
    Example: MAT-12345, MCN-001, PFC-00001
    """
    if not code:
        return None

    parts = code.split("-")
    if len(parts) < 2:
        return None

    prefix = parts[0].upper()
    qr_id = "-".join(parts[1:])  # Handle IDs with dashes

    qr_type = get_qr_type(code)
    if not qr_type:
        return None

    try:
        return {
            "type": qr_type,
            "prefix": prefix,
            "id": qr_id,
            "original_code": code,
        }
    except (ValueError, TypeError):
        return None


def generate_qr_content(qr_type: QRType, entity_id: str | int) -> str:
    """Generate QR code content URL for given type and ID."""
    domain = getattr(settings, 'QR_DOMAIN', 'erp.example.com')
    content = QR_CONTENT_TEMPLATE[qr_type]
    return content.format(domain=domain, id=entity_id)


def generate_qr_code(
    content: str,
    box_size: int = 10,
    border: int = 4,
    error_correction: int = 2,  # M (15%)
    fit: bool = True,
) -> bytes:
    """
    Generate QR code image as PNG bytes.

    Args:
        content: URL or text to encode
        box_size: Size of each QR module
        border: Width of border (modules)
        error_correction: 0=L, 1=M, 2=Q, 3=H
        fit: Fit to content

    Returns:
        PNG image bytes
    """
    if not QRCODE_AVAILABLE:
        raise ImportError("qrcode and PIL libraries required. Install: pip install qrcode[pil] pillow")

    # QR error correction levels
    ec_level_map = {
        0: qrcode.constants.ERROR_CORRECT_L,  # 7%
        1: qrcode.constants.ERROR_CORRECT_M,     # 15%
        2: qrcode.constants.ERROR_CORRECT_Q,     # 25%
        3: qrcode.constants.ERROR_CORRECT_H,     # 30%
    }

    qr = qrcode.QRCode(
        version=None,
        error_correction=ec_level_map.get(error_correction, qrcode.constants.ERROR_CORRECT_M),
        box_size=box_size,
        border=border,
        image_factory=None,
        mask_pattern=None,
    )

    qr.add_data(content)
    qr.make(fit=fit)

    img = qr.make_image(fill_color="black", back_color="white")
    img_buffer = io.BytesIO()
    img.save(img_buffer, format="PNG")
    return img_buffer.getvalue()


def generate_qr_with_logo(
    content: str,
    logo_path: Optional[str] = None,
    logo_size: int = 80,
    box_size: int = 10,
) -> bytes:
    """
    Generate QR code with logo in center.

    Args:
        content: URL or text to encode
        logo_path: Path to logo image file
        logo_size: Size of logo in pixels
        box_size: Size of each QR module

    Returns:
        PNG image bytes
    """
    if not QRCODE_AVAILABLE:
        raise ImportError("qrcode and PIL libraries required. Install: pip install qrcode[pil] pillow")

    # Generate base QR code
    qr_bytes = generate_qr_code(content, box_size=box_size)
    qr_img = Image.open(io.BytesIO(qr_bytes))

    # Add logo if provided
    if logo_path:
        try:
            logo = Image.open(logo_path)
            logo_size_px = min(logo_size, qr_img.size[0] // 5)

            # Calculate logo position (center)
            logo = logo.convert("RGBA")
            logo.thumbnail((logo_size_px, logo_size_px), Image.LANCZOS)

            # Create white background for logo
            logo_bg = Image.new("RGBA", logo.size, (255, 255, 255, 255))
            logo_bg.paste(logo, mask=logo)

            # Calculate position
            x = (qr_img.size[0] - logo.size[0]) // 2
            y = (qr_img.size[1] - logo.size[1]) // 2

            # Paste logo on QR code
            qr_img.paste(logo_bg, (x, y), mask=logo_bg)
        except Exception:
            pass  # Skip logo if error

    # Save to bytes
    img_buffer = io.BytesIO()
    qr_img.save(img_buffer, format="PNG")
    return img_buffer.getvalue()


def generate_qr_base64(
    content: str,
    box_size: int = 10,
) -> str:
    """
    Generate QR code as base64 string (data URI).

    Returns:
        Base64 data URI: data:image/png;base64,{base64_string}
    """
    qr_bytes = generate_qr_code(content, box_size=box_size)
    base64_str = base64.b64encode(qr_bytes).decode("utf-8")
    return f"data:image/png;base64,{base64_str}"


def generate_material_qr(batch_id: str | int) -> tuple[bytes, str]:
    """
    Generate QR code for material batch.

    Returns:
        (PNG bytes, QR code string MAT-{id})
    """
    qr_code = f"MAT-{batch_id}"
    content = generate_qr_content(QRType.MATERIAL, batch_id)
    qr_bytes = generate_qr_code(content)
    return qr_bytes, qr_code


def generate_machine_qr(machine_id: str | int) -> tuple[bytes, str]:
    """
    Generate QR code for machine.

    Returns:
        (PNG bytes, QR code string MCN-{id})
    """
    qr_code = f"MCN-{machine_id}"
    content = generate_qr_content(QRType.MACHINE, machine_id)
    qr_bytes = generate_qr_code(content)
    return qr_bytes, qr_code


def generate_process_flow_qr(card_id: str | int) -> tuple[bytes, str]:
    """
    Generate QR code for process flow card.

    Returns:
        (PNG bytes, QR code string PFC-{id})
    """
    qr_code = f"PFC-{card_id}"
    content = generate_qr_content(QRType.PROCESS_FLOW, card_id)
    qr_bytes = generate_qr_code(content)
    return qr_bytes, qr_code


def generate_part_qr(part_id: str | int) -> tuple[bytes, str]:
    """
    Generate QR code for part.

    Returns:
        (PNG bytes, QR code string PRT-{id})
    """
    qr_code = f"PRT-{part_id}"
    content = generate_qr_content(QRType.PART, part_id)
    qr_bytes = generate_qr_code(content)
    return qr_bytes, qr_code


def generate_packaging_qr(record_id: str | int) -> tuple[bytes, str]:
    """
    Generate QR code for packaging record.

    Returns:
        (PNG bytes, QR code string PKG-{id})
    """
    qr_code = f"PKG-{record_id}"
    content = generate_qr_content(QRType.PACKAGING, record_id)
    qr_bytes = generate_qr_code(content)
    return qr_bytes, qr_code
