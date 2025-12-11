from typing import Any, Dict, Optional
import hashlib
from src.business_logic.base_service import BaseService
from src.database.daos import 用户表DAO


class UserService(BaseService):
    """
    用户管理服务：登录验证、用户查询等。
    """

    def __init__(self) -> None:
        super().__init__()
        self.user_dao = 用户表DAO()

    def _hash_password(self, password: str) -> str:
        """使用SHA256哈希密码（生产环境建议使用bcrypt）"""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """验证密码"""
        return self._hash_password(password) == hashed_password

    def authenticate(self, username: str, password: str) -> Dict[str, Any]:
        """
        验证用户登录
        返回: {'success': bool, 'message': str, 'data': {user_id, username, position} or None}
        """
        try:
            username = (username or '').strip()
            password = (password or '').strip()
            
            if not username or not password:
                return self._create_error_response("用户名和密码不能为空")
            
            user = self.user_dao.get_by_username(username)
            if not user:
                return self._create_error_response("用户名或密码错误")
            
            # 验证密码
            stored_password = user.get('密码', '')
            if not self.verify_password(password, stored_password):
                return self._create_error_response("用户名或密码错误")
            
            # 返回用户信息（不包含密码）
            user_data = {
                'user_id': user.get('用户id'),
                'username': user.get('用户名'),
                'position': user.get('职位'),
            }
            return self._create_success_response(data=user_data, message="登录成功")
        except Exception as e:
            return self._create_error_response(f"登录验证失败: {str(e)}")

    def get_user_by_id(self, user_id: int) -> Dict[str, Any]:
        """根据ID获取用户信息（不包含密码）"""
        try:
            user = self.user_dao.get_by_id(user_id)
            if not user:
                return self._create_error_response("用户不存在")
            
            user_data = {
                'user_id': user.get('用户id'),
                'username': user.get('用户名'),
                'position': user.get('职位'),
                'created_at': user.get('创建时间'),
            }
            return self._create_success_response(data=user_data)
        except Exception as e:
            return self._create_error_response(f"获取用户信息失败: {str(e)}")

    def create_user(self, username: str, password: str, position: str) -> Dict[str, Any]:
        """
        创建新用户（仅管理员可用）
        """
        try:
            username = (username or '').strip()
            password = (password or '').strip()
            position = (position or '').strip()
            
            if not username or not password:
                return self._create_error_response("用户名和密码不能为空")
            
            # 检查用户名是否已存在
            existing = self.user_dao.get_by_username(username)
            if existing:
                return self._create_error_response("用户名已存在")
            
            # 创建用户
            hashed_password = self._hash_password(password)
            user_data = {
                '用户名': username,
                '密码': hashed_password,
                '职位': position,
            }
            
            new_id = self.user_dao.create(user_data)
            if not new_id:
                return self._create_error_response("创建用户失败")
            
            return self._create_success_response(
                data={'user_id': new_id}, 
                message="用户创建成功"
            )
        except Exception as e:
            return self._create_error_response(f"创建用户失败: {str(e)}")

    # ===== 新增：账号重置与密码修改 =====
    def create_or_reset_user(self, username: str, password: str, position: str) -> Dict[str, Any]:
        """
        管理员给员工设置初始账号或重置账号密码。
        - 若用户名不存在：创建新账号
        - 若用户名已存在：更新密码与职位
        """
        try:
            username = (username or '').strip()
            password = (password or '').strip()
            position = (position or '').strip()
            if not username or not password:
                return self._create_error_response("用户名和密码不能为空")

            hashed_password = self._hash_password(password)
            existing = self.user_dao.get_by_username(username)
            if existing:
                ok = self.user_dao.update(existing['用户id'], {
                    '密码': hashed_password,
                    '职位': position,
                })
                if not ok:
                    return self._create_error_response("账号重置失败")
                return self._create_success_response(
                    data={'user_id': existing['用户id']},
                    message="账号已重置"
                )
            # 创建新账号
            new_id = self.user_dao.create({
                '用户名': username,
                '密码': hashed_password,
                '职位': position,
            })
            if not new_id:
                return self._create_error_response("创建账号失败")
            return self._create_success_response(
                data={'user_id': new_id},
                message="账号已创建"
            )
        except Exception as e:
            return self._create_error_response(f"账号设置失败: {str(e)}")

    def change_password(self, user_id: int, old_password: str, new_password: str) -> Dict[str, Any]:
        """
        用户自助修改密码：需要验证旧密码
        """
        try:
            old_password = (old_password or '').strip()
            new_password = (new_password or '').strip()
            if not old_password or not new_password:
                return self._create_error_response("旧密码和新密码不能为空")
            if len(new_password) < 6:
                return self._create_error_response("新密码长度至少6位")

            user = self.user_dao.get_by_id(user_id)
            if not user:
                return self._create_error_response("用户不存在")

            if not self.verify_password(old_password, user.get('密码', '')):
                return self._create_error_response("旧密码错误")

            hashed = self._hash_password(new_password)
            ok = self.user_dao.update(user_id, {'密码': hashed})
            if not ok:
                return self._create_error_response("修改密码失败")
            return self._create_success_response(message="密码已更新")
        except Exception as e:
            return self._create_error_response(f"修改密码失败: {str(e)}")

    def admin_reset_password(self, username: str, new_password: str, position: Optional[str] = None) -> Dict[str, Any]:
        """
        管理员直接重置指定用户名的密码，并可同步更新职位。
        """
        try:
            username = (username or '').strip()
            new_password = (new_password or '').strip()
            if not username or not new_password:
                return self._create_error_response("用户名和新密码不能为空")

            user = self.user_dao.get_by_username(username)
            if not user:
                return self._create_error_response("用户不存在")
            update_fields = {'密码': self._hash_password(new_password)}
            if position:
                update_fields['职位'] = position.strip()
            ok = self.user_dao.update(user['用户id'], update_fields)
            if not ok:
                return self._create_error_response("重置密码失败")
            return self._create_success_response(message="密码已重置")
        except Exception as e:
            return self._create_error_response(f"重置密码失败: {str(e)}")

    def update_position_by_username(self, username: str, new_position: str) -> Dict[str, Any]:
        """
        将指定用户名的职位更新为 new_position。
        若用户不存在则返回成功（视为无需更新）。
        """
        try:
            username = (username or '').strip()
            new_position = (new_position or '').strip()
            if not username or not new_position:
                return self._create_error_response("用户名和新职位不能为空")

            user = self.user_dao.get_by_username(username)
            if not user:
                # 没有对应账号，视为无需同步
                return self._create_success_response(message="无对应账号，无需同步职位")

            ok = self.user_dao.update(user['用户id'], {'职位': new_position})
            if not ok:
                return self._create_error_response("更新用户职位失败")
            return self._create_success_response(message="用户职位已同步更新")
        except Exception as e:
            return self._create_error_response(f"更新用户职位失败: {str(e)}")

