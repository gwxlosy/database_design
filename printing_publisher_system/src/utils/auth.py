"""
权限验证工具模块
提供登录检查和权限装饰器
"""
from functools import wraps
from flask import session, redirect, url_for, flash, request
from typing import Callable, Optional, Iterable

from src.business_logic.user_service import UserService


def _get_user_service() -> UserService:
    """懒加载 UserService，避免循环导入问题。"""
    return UserService()


def _refresh_user_in_session() -> Optional[dict]:
    """从数据库刷新用户信息，返回 data 或 None。"""
    if 'user_id' not in session:
        return None
    user_service = _get_user_service()
    info = user_service.get_user_by_id(session.get('user_id'))
    if not info.get('success'):
        session.clear()
        return None
    data = info.get('data', {})
    session['username'] = data.get('username')
    session['position'] = data.get('position')
    return data


def _has_position(allowed_positions: Iterable[str]) -> bool:
    """检查当前用户是否属于允许的职位集合（实时从数据库校验）。"""
    data = _refresh_user_in_session()
    if not data:
        return False
    return data.get('position') in set(allowed_positions)


def login_required(f: Callable) -> Callable:
    """
    登录检查装饰器
    如果用户未登录，重定向到登录页面
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'username' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def admin_required(f: Callable) -> Callable:
    """
    管理员权限检查装饰器
    只有职位为"管理员"的用户才能访问
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or 'username' not in session:
            flash('请先登录', 'warning')
            return redirect(url_for('login', next=request.url))

        # 每次从数据库校验职位，避免改完职位仍保留旧的管理员权限
        if not _has_position({"管理员"}):
            flash('您没有权限执行此操作', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


def roles_required(positions: Iterable[str]) -> Callable:
    """允许指定职位访问的装饰器。"""
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def wrapped(*args, **kwargs):
            if 'user_id' not in session or 'username' not in session:
                flash('请先登录', 'warning')
                return redirect(url_for('login', next=request.url))
            if not _has_position(positions):
                flash('您没有权限执行此操作', 'error')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapped
    return decorator


def get_current_user() -> Optional[dict]:
    """
    获取当前登录用户信息
    返回: {'user_id': int, 'username': str, 'position': str} 或 None
    """
    if 'user_id' not in session:
        return None

    # 优先返回 session 缓存
    cached = {
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'position': session.get('position'),
    }
    if cached.get('username') and cached.get('position'):
        return cached

    data = _refresh_user_in_session()
    if not data:
        return None
    return {
        'user_id': session.get('user_id'),
        'username': session.get('username'),
        'position': session.get('position'),
    }


def is_admin() -> bool:
    """检查当前用户是否是管理员（实时查询，防止权限滞后）"""
    return _has_position({"管理员"})


def is_print_operator() -> bool:
    """印刷任务相关操作权限：管理员或印刷工。"""
    return _has_position({"管理员", "印刷工"})


def is_editor_or_admin() -> bool:
    """检查当前用户是否为编辑或管理员。"""
    return _has_position({"管理员", "编辑"})


def is_material_manager() -> bool:
    """材料/供应商增改权限：管理员 或 采购。"""
    return _has_position({"管理员", "采购"})


def is_inventory_operator() -> bool:
    """库存操作权限：管理员 或 采购 或 仓储。"""
    return _has_position({"管理员", "采购", "仓储"})

