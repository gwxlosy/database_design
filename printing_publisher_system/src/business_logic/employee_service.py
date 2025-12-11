from datetime import date, datetime
from typing import Any, Dict, Optional
from src.business_logic.base_service import BaseService
from src.database.daos import 员工DAO
from src.database.models import EmployeeModel, model_to_db_dict, dict_to_model
from src.business_logic.user_service import UserService


class EmployeeService(BaseService):
    """
    员工管理服务：分页查询、创建、更新、删除与状态变更。
    采用领域模型做字段映射，屏蔽数据库中文列名。
    """

    def __init__(self) -> None:
        super().__init__()
        self.employee_dao = 员工DAO()

    def list_employees_page(self, page: int = 1, page_size: int = 10,
                            status: Optional[str] = None,
                            position: Optional[str] = None,
                            name: Optional[str] = None) -> Dict[str, Any]:
        try:
            page_data = self.employee_dao.get_page_by_filters(
                name_kw=name,
                status=status,
                position=position,
                order_by="入职日期 DESC",
                page=page,
                page_size=page_size,
            )
            return self._create_success_response(data=page_data)
        except Exception as e:
            return self._create_error_response(f"获取员工分页失败: {str(e)}")

    def create_employee(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        data: 期望英文键：name, position, status（'在职'/'离职'），可扩展
        """
        try:
            name = (data.get('name') or '').strip()
            position = (data.get('position') or '').strip()
            status = (data.get('status') or '在职').strip()
            if not name:
                return self._create_error_response("员工姓名不能为空")
            if status not in ('在职', '离职'):
                return self._create_error_response("状态必须是 在职/离职")

            # 通过模型映射到中文列，若未提供入职日期则默认今日
            payload = {'name': name, 'position': position, 'status': status}
            hired = data.get('hired_at')
            if not hired:
                hired = date.today()
            if EmployeeModel is not None:
                # type: ignore
                model = EmployeeModel(**{
                    '员工id': None,
                    '员工姓名': name,
                    '职位': position,
                    '在职状态': status,
                    '入职日期': hired,
                })  # 使用 alias 构造
                db_row = model_to_db_dict(model)
            else:
                db_row = {'员工姓名': name, '职位': position, '在职状态': status, '入职日期': hired}

            new_id = self.employee_dao.create(db_row)
            if not new_id:
                return self._create_error_response("创建员工失败")
            return self._create_success_response(data={'employee_id': new_id}, message="员工创建成功")
        except Exception as e:
            return self._create_error_response(f"创建员工失败: {str(e)}")

    def update_employee(self, employee_id: int, data: Dict[str, Any]) -> Dict[str, Any]:
        try:
            # 记录更新前的姓名和职位，便于同步账号权限
            before = self.employee_dao.get_by_id(employee_id) or {}
            update_fields: Dict[str, Any] = {}
            if 'name' in data:
                if not str(data['name']).strip():
                    return self._create_error_response("员工姓名不能为空")
                update_fields['员工姓名'] = str(data['name']).strip()
            if 'position' in data:
                update_fields['职位'] = str(data['position']).strip()
            if 'status' in data:
                if data['status'] not in ('在职', '离职'):
                    return self._create_error_response("状态必须是 在职/离职")
                update_fields['在职状态'] = data['status']
            if not update_fields:
                return self._create_error_response("没有可更新的字段")

            ok = self.employee_dao.update(employee_id, update_fields)
            if not ok:
                return self._create_error_response("更新员工失败")

            # 同步用户账号职位（假设用户名与员工姓名一致）
            new_name = update_fields.get('员工姓名') or before.get('员工姓名')
            new_position = update_fields.get('职位') or before.get('职位')
            if new_name and new_position:
                try:
                    user_service = UserService()
                    user_service.update_position_by_username(new_name, new_position)
                    # 若姓名变化，也尝试用旧姓名同步一次
                    if before.get('员工姓名') and before.get('员工姓名') != new_name:
                        user_service.update_position_by_username(before.get('员工姓名'), new_position)
                except Exception:
                    # 不影响主流程
                    pass
            return self._create_success_response(message="员工信息已更新")
        except Exception as e:
            return self._create_error_response(f"更新员工失败: {str(e)}")

    def delete_employee(self, employee_id: int) -> Dict[str, Any]:
        try:
            ok = self.employee_dao.delete(employee_id)
            if not ok:
                return self._create_error_response("删除员工失败，可能不存在或有外键约束")
            return self._create_success_response(message="员工已删除")
        except Exception as e:
            return self._create_error_response(f"删除员工失败: {str(e)}")

    def change_status(self, employee_id: int, new_status: str) -> Dict[str, Any]:
        try:
            if new_status not in ('在职', '离职'):
                return self._create_error_response("状态必须是 在职/离职")
            ok = self.employee_dao.update_employment_status(employee_id, new_status)
            if not ok:
                return self._create_error_response("状态更新失败")
            return self._create_success_response(message="状态已更新")
        except Exception as e:
            return self._create_error_response(f"状态更新失败: {str(e)}")

    def get_employee(self, employee_id: int) -> Dict[str, Any]:
        """按id获取员工信息"""
        try:
            row = self.employee_dao.get_by_id(employee_id)
            if not row:
                return self._create_error_response("员工不存在")
            # 若需要模型，可转为模型再返回
            return self._create_success_response(data=row)
        except Exception as e:
            return self._create_error_response(f"获取员工失败: {str(e)}")

