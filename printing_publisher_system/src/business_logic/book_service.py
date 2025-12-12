from typing import Any, Dict, Optional
from src.business_logic.base_service import BaseService
from src.database.daos import 书籍核心信息DAO, 书籍版本DAO


class BookService(BaseService):
    """
    书籍信息与版本管理服务
    - 书籍核心信息的增查
    - 书籍版本的增查
    """

    def __init__(self) -> None:
        super().__init__()
        self.book_dao = 书籍核心信息DAO()
        self.version_dao = 书籍版本DAO()

    # ========= 书籍 =========
    def list_books(self, name_kw: Optional[str] = None, author: Optional[str] = None, sort: Optional[str] = None) -> Dict[str, Any]:
        try:
            # 允许的排序键
            sort_map = {
                'id_asc': '书籍id ASC',
                'id_desc': '书籍id DESC',
                'name_alpha': '书籍名称 ASC',  # 简单按名称升序，视为按首字母排序
            }
            order_by = sort_map.get((sort or '').strip()) or '书籍id ASC'

            filters: Dict[str, Any] = {}
            if author:
                filters["作者"] = author
            if name_kw:
                # 模糊查询 + 排序
                query = f"SELECT * FROM 书籍核心信息表 WHERE 书籍名称 LIKE %s"
                if author:
                    query += " AND 作者 = %s"
                query += f" ORDER BY {order_by}"
                params = [f"%{name_kw}%"]
                if author:
                    params.append(author)
                with self.book_dao.db.get_cursor() as cursor:  # type: ignore
                    cursor.execute(query, tuple(params))
                    items = cursor.fetchall()
            else:
                items = self.book_dao.get_all(filters=filters, order_by=order_by)
            return self._create_success_response(data={"items": items})
        except Exception as e:
            return self._create_error_response(f"获取书籍列表失败: {str(e)}")

    def create_book(self, name: str, author: str) -> Dict[str, Any]:
        try:
            name = (name or "").strip()
            author = (author or "").strip()
            if not name:
                return self._create_error_response("书籍名称不能为空")
            payload = {"书籍名称": name, "作者": author}
            new_id = self.book_dao.create(payload)
            if not new_id:
                return self._create_error_response("创建书籍失败")
            return self._create_success_response(data={"book_id": new_id}, message="书籍创建成功")
        except Exception as e:
            return self._create_error_response(f"创建书籍失败: {str(e)}")

    def get_book(self, book_id: int) -> Dict[str, Any]:
        try:
            row = self.book_dao.get_by_id(book_id)
            if not row:
                return self._create_error_response("书籍不存在")
            return self._create_success_response(data=row)
        except Exception as e:
            return self._create_error_response(f"获取书籍失败: {str(e)}")

    # ========= 版本 =========
    def list_versions(self, book_id: int) -> Dict[str, Any]:
        try:
            items = self.version_dao.get_versions_by_book_id(book_id)
            return self._create_success_response(data={"items": items})
        except Exception as e:
            return self._create_error_response(f"获取书籍版本失败: {str(e)}")

    def list_versions_all(self) -> Dict[str, Any]:
        """获取全部版本，用于选择。"""
        try:
            items = self.version_dao.get_all(order_by="书籍id ASC, 版本创建日期 DESC")
            return self._create_success_response(data={"items": items})
        except Exception as e:
            return self._create_error_response(f"获取版本列表失败: {str(e)}")

    def create_version(
        self,
        book_id: int,
        version_desc: str,
        isbn: str,
        pages: int,
        format_text: Optional[str],
        created_date: Optional[str],
    ) -> Dict[str, Any]:
        try:
            version_desc = (version_desc or "").strip()
            isbn = (isbn or "").strip()
            format_text = (format_text or "").strip()
            created_date = (created_date or "").strip()
            if not version_desc:
                return self._create_error_response("版本描述不能为空")
            if not isbn:
                return self._create_error_response("ISBN不能为空")
            try:
                pages_int = int(pages)
            except Exception:
                return self._create_error_response("版本页数必须是正整数")
            if pages_int <= 0:
                return self._create_error_response("版本页数必须大于0")
            payload: Dict[str, Any] = {
                "书籍id": book_id,
                "国际标准书号": isbn,
                "版本描述": version_desc,
            }
            if format_text:
                payload["开本"] = format_text
            payload["页数"] = pages_int
            if created_date:
                payload["版本创建日期"] = created_date
            new_id = self.version_dao.create(payload)
            if not new_id:
                return self._create_error_response("创建书籍版本失败")
            return self._create_success_response(data={"book_version_id": new_id}, message="版本创建成功")
        except Exception as e:
            return self._create_error_response(f"创建书籍版本失败: {str(e)}")

