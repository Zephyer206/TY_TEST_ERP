"""
app/services/cos_service.py
腾讯云 COS 对象存储服务
"""
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# 腾讯云 COS SDK
try:
    from qcloud_cos import CosConfig
    from qcloud_cos import CosS3Client
    COS_SDK_AVAILABLE = True
except ImportError:
    COS_SDK_AVAILABLE = False
    logger.warning("腾讯云 COS SDK 未安装，将使用本地存储")


class COSService:
    """腾讯云 COS 服务封装"""

    def __init__(self):
        self.enabled = os.environ.get('COS_ENABLED', 'false').lower() == 'true'
        self.client = None

        if self.enabled and COS_SDK_AVAILABLE:
            self._init_client()
        elif self.enabled and not COS_SDK_AVAILABLE:
            logger.warning("COS_ENABLED=true 但 SDK 未安装，将使用本地存储")
            self.enabled = False

    def _init_client(self):
        """初始化 COS 客户端"""
        try:
            secret_id = os.environ.get('COS_SECRET_ID')
            secret_key = os.environ.get('COS_SECRET_KEY')
            region = os.environ.get('COS_REGION', 'ap-guangzhou')

            if not secret_id or not secret_key:
                logger.error("COS_SECRET_ID 或 COS_SECRET_KEY 未设置")
                self.enabled = False
                return

            config = CosConfig(
                Region=region,
                SecretId=secret_id,
                SecretKey=secret_key,
            )
            self.client = CosS3Client(config)
            logger.info(f"COS 客户端初始化成功: region={region}")
        except Exception as e:
            logger.error(f"COS 客户端初始化失败: {e}")
            self.enabled = False

    def upload_file(self, local_path: str, cos_key: str) -> str:
        """上传文件到 COS

        Args:
            local_path: 本地文件路径
            cos_key: COS 存储路径（如 'uploads/parts/123.png'）

        Returns:
            COS 访问 URL 或本地路径
        """
        if not self.enabled:
            # 降级到本地存储
            return local_path

        try:
            bucket = os.environ.get('COS_BUCKET', 'zephyr-erp')
            response = self.client.put_object_from_local_file(
                Bucket=bucket,
                LocalFilePath=local_path,
                Key=cos_key,
            )
            logger.info(f"文件上传成功: {cos_key}")
            # 返回 CDN 访问地址
            endpoint = os.environ.get('COS_ENDPOINT', 'https://cos.ap-guangzhou.myqcloud.com')
            return f"{endpoint}/{bucket}/{cos_key}"
        except Exception as e:
            logger.error(f"COS 上传失败: {e}")
            # 降级到本地存储
            return local_path

    def upload_bytes(self, data: bytes, cos_key: str, content_type: str = 'image/png') -> str:
        """上传字节数据到 COS

        Args:
            data: 文件字节数据
            cos_key: COS 存储路径
            content_type: 内容类型

        Returns:
            COS 访问 URL
        """
        if not self.enabled:
            return None

        try:
            bucket = os.environ.get('COS_BUCKET', 'zephyr-erp')
            from io import BytesIO
            response = self.client.put_object(
                Bucket=bucket,
                Body=BytesIO(data),
                Key=cos_key,
                ContentType=content_type,
            )
            logger.info(f"字节数据上传成功: {cos_key}")
            endpoint = os.environ.get('COS_ENDPOINT', 'https://cos.ap-guangzhou.myqcloud.com')
            return f"{endpoint}/{bucket}/{cos_key}"
        except Exception as e:
            logger.error(f"COS 字节上传失败: {e}")
            return None

    def generate_presigned_url(self, cos_key: str, expire_seconds: int = 3600) -> str:
        """生成预签名 URL（用于临时访问）

        Args:
            cos_key: COS 存储路径
            expire_seconds: 过期时间（秒）

        Returns:
            预签名 URL
        """
        if not self.enabled or not self.client:
            return None

        try:
            bucket = os.environ.get('COS_BUCKET', 'zephyr-erp')
            response = self.client.generate_download_url(
                Bucket=bucket,
                Key=cos_key,
                Expired=expire_seconds,
            )
            return response['Url']
        except Exception as e:
            logger.error(f"生成预签名 URL 失败: {e}")
            return None

    def delete_file(self, cos_key: str) -> bool:
        """删除 COS 文件"""
        if not self.enabled:
            return True

        try:
            bucket = os.environ.get('COS_BUCKET', 'zephyr-erp')
            self.client.delete_object(Bucket=bucket, Key=cos_key)
            logger.info(f"文件删除成功: {cos_key}")
            return True
        except Exception as e:
            logger.error(f"COS 文件删除失败: {e}")
            return False

    def file_exists(self, cos_key: str) -> bool:
        """检查文件是否存在"""
        if not self.enabled:
            return os.path.exists(cos_key)

        try:
            bucket = os.environ.get('COS_BUCKET', 'zephyr-erp')
            self.client.head_object(Bucket=bucket, Key=cos_key)
            return True
        except:
            return False


# 全局单例
cos_service = COSService()


def get_cos_service() -> COSService:
    """获取 COS 服务实例"""
    return cos_service
