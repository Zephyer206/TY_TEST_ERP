"""
Cloud OSS storage service for QR codes and file uploads.

Supports:
- Tencent Cloud COS (COS)
- Alibaba Cloud OSS

QR code images can be uploaded to cloud storage for CDN distribution.
"""

import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from urllib.parse import urljoin

try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False

try:
    import oss2
    OSS2_AVAILABLE = True
except ImportError:
    OSS2_AVAILABLE = False

from app.core.config import settings


class BaseStorage(ABC):
    """Abstract base class for cloud storage."""

    @abstractmethod
    def upload_file(self, file_data: bytes, object_key: str) -> str:
        """Upload file and return URL."""
        pass

    @abstractmethod
    def delete_file(self, object_key: str) -> bool:
        """Delete file and return success status."""
        pass

    @abstractmethod
    def get_presigned_url(self, object_key: str, expires: int = 3600) -> str:
        """Get presigned URL for temporary access."""
        pass


class TencentCOSStorage(BaseStorage):
    """Tencent Cloud COS storage implementation."""

    def __init__(
        self,
        secret_id: Optional[str] = None,
        secret_key: Optional[str] = None,
        region: Optional[str] = None,
        bucket: Optional[str] = None,
    ):
        if not BOTO3_AVAILABLE:
            raise ImportError("boto3 required for Tencent COS. Install: pip install boto3")

        self.secret_id = secret_id or os.getenv("TENCENT_SECRET_ID", "")
        self.secret_key = secret_key or os.getenv("TENCENT_SECRET_KEY", "")
        self.region = region or os.getenv("TENCENT_REGION", "ap-guangzhou")
        self.bucket = bucket or os.getenv("TENCENT_COS_BUCKET", "")

        self.bucket_name = self.bucket
        self.client = None

        if self.secret_id and self.secret_key and self.bucket:
            self.client = boto3.client(
                's3',
                region_name=self.region,
                aws_access_key_id=self.secret_id,
                aws_secret_access_key=self.secret_key,
            )

    def _get_bucket_url(self) -> str:
        """Get bucket URL."""
        return f"https://{self.bucket_name}.cos.{self.region}.myqcloud.com"

    def upload_file(self, file_data: bytes, object_key: str) -> str:
        """Upload file to COS."""
        if not self.client:
            raise RuntimeError("COS client not configured")

        try:
            self.client.put_object(
                Bucket=self.bucket_name,
                Body=file_data,
                Key=object_key,
                ContentType='image/png',
            )
            return f"{self._get_bucket_url()}/{object_key}"
        except ClientError as e:
            raise RuntimeError(f"Failed to upload to COS: {e}")

    def delete_file(self, object_key: str) -> bool:
        """Delete file from COS."""
        if not self.client:
            raise RuntimeError("COS client not configured")

        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_key)
            return True
        except ClientError:
            return False

    def get_presigned_url(self, object_key: str, expires: int = 3600) -> str:
        """Get presigned URL from COS."""
        if not self.client:
            raise RuntimeError("COS client not configured")

        try:
            url = self.client.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket_name, 'Key': object_key},
                ExpiresIn=expires,
            )
            return url
        except ClientError:
            return f"{self._get_bucket_url()}/{object_key}"


class AlibabaOSSStorage(BaseStorage):
    """Alibaba Cloud OSS storage implementation."""

    def __init__(
        self,
        access_key_id: Optional[str] = None,
        access_key_secret: Optional[str] = None,
        region: Optional[str] = None,
        bucket: Optional[str] = None,
    ):
        if not OSS2_AVAILABLE:
            raise ImportError("oss2 required for Alibaba OSS. Install: pip install oss2")

        self.access_key_id = access_key_id or os.getenv("ALIYUN_ACCESS_KEY_ID", "")
        self.access_key_secret = access_key_secret or os.getenv("ALIYUN_ACCESS_KEY_SECRET", "")
        self.region = region or os.getenv("ALIYUN_REGION", "oss-cn-hangzhou")
        self.bucket_name = bucket or os.getenv("ALIYUN_OSS_BUCKET", "")

        self.bucket = None

        if self.access_key_id and self.access_key_secret and self.bucket_name:
            auth = oss2.Auth(self.access_key_id, self.access_key_secret)
            endpoint = f"https://oss-{self.region}.aliyuncs.com"
            self.bucket = oss2.Bucket(auth, endpoint, self.bucket_name)

    def _get_bucket_url(self) -> str:
        """Get bucket URL."""
        return f"https://{self.bucket_name}.oss-{self.region}.aliyuncs.com"

    def upload_file(self, file_data: bytes, object_key: str) -> str:
        """Upload file to OSS."""
        if not self.bucket:
            raise RuntimeError("OSS bucket not configured")

        try:
            self.bucket.put_object(object_key, file_data, content_type='image/png')
            return f"{self._get_bucket_url()}/{object_key}"
        except oss2.exceptions.OssError as e:
            raise RuntimeError(f"Failed to upload to OSS: {e}")

    def delete_file(self, object_key: str) -> bool:
        """Delete file from OSS."""
        if not self.bucket:
            raise RuntimeError("OSS bucket not configured")

        try:
            self.bucket.delete_object(object_key)
            return True
        except oss2.exceptions.OssError:
            return False

    def get_presigned_url(self, object_key: str, expires: int = 3600) -> str:
        """Get presigned URL from OSS."""
        if not self.bucket:
            raise RuntimeError("OSS bucket not configured")

        try:
            url = self.bucket.sign_url('GET', object_key, expires)
            return url
        except oss2.exceptions.OssError:
            return f"{self._get_bucket_url()}/{object_key}"


class LocalStorage(BaseStorage):
    """Local file storage (fallback for development)."""

    def __init__(self, base_path: Optional[str] = None):
        self.base_path = base_path or os.getenv("LOCAL_STORAGE_PATH", "./uploads")
        os.makedirs(self.base_path, exist_ok=True)

    def _get_base_url(self) -> str:
        """Get base URL."""
        return os.getenv("LOCAL_STORAGE_URL", "http://localhost:8000/uploads")

    def upload_file(self, file_data: bytes, object_key: str) -> str:
        """Save file to local disk."""
        file_path = os.path.join(self.base_path, object_key)
        os.makedirs(os.path.dirname(file_path), exist_ok=True)

        with open(file_path, 'wb') as f:
            f.write(file_data)

        return f"{self._get_base_url()}/{object_key}"

    def delete_file(self, object_key: str) -> bool:
        """Delete file from local disk."""
        try:
            file_path = os.path.join(self.base_path, object_key)
            if os.path.exists(file_path):
                os.remove(file_path)
            return True
        except Exception:
            return False

    def get_presigned_url(self, object_key: str, expires: int = 3600) -> str:
        """Get URL for local file (expires param ignored)."""
        return f"{self._get_base_url()}/{object_key}"


def get_storage() -> BaseStorage:
    """
    Get configured storage backend.

    Priority:
    1. Tencent Cloud COS (if TENCENT_SECRET_ID set)
    2. Alibaba Cloud OSS (if ALIYUN_ACCESS_KEY_ID set)
    3. Local storage (default for development)
    """
    if os.getenv("TENCENT_SECRET_ID"):
        return TencentCOSStorage()

    if os.getenv("ALIYUN_ACCESS_KEY_ID"):
        return AlibabaOSSStorage()

    return LocalStorage()


def generate_qr_storage_path(qr_type: str, entity_id: str) -> str:
    """Generate storage path for QR code image."""
    date_str = datetime.utcnow().strftime("%Y%m")
    return f"qr/{qr_type}/{date_str}/{qr_type}-{entity_id}.png"


# Global storage instance
_storage: Optional[BaseStorage] = None


def get_oss_storage() -> BaseStorage:
    """Get or create global storage instance."""
    global _storage
    if _storage is None:
        _storage = get_storage()
    return _storage


async def upload_qr_to_cloud(qr_type: str, entity_id: str, qr_bytes: bytes) -> str:
    """
    Upload QR code image to cloud storage.

    Returns public URL of uploaded image.
    """
    storage = get_oss_storage()
    object_key = generate_qr_storage_path(qr_type, entity_id)
    return storage.upload_file(qr_bytes, object_key)
