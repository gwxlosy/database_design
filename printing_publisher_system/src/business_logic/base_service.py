from abc import ABC
from typing import Dict, Any, Optional
import logging

class BaseService(ABC):
    """
    业务逻辑服务类的基类，提供通用功能。
    """
    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def _validate_required_fields(self, data: Dict[str, Any], required_fields: list) -> Optional[Dict[str, Any]]:
        """验证必需字段的通用方法"""
        missing_fields = [field for field in required_fields if field not in data or data[field] is None]
        if missing_fields:
            error_msg = f"缺少必需字段: {', '.join(missing_fields)}"
            self.logger.warning(error_msg)
            return {'success': False, 'message': error_msg}
        return None

    def _create_error_response(self, message: str) -> Dict[str, Any]:
        """创建统一的错误响应"""
        self.logger.error(message)
        return {'success': False, 'message': message}

    def _create_success_response(self, data: Any = None, message: str = "操作成功") -> Dict[str, Any]:
        """创建统一的成功响应"""
        response = {'success': True, 'message': message}
        if data is not None:
            response['data'] = data
        return response