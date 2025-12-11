from __future__ import annotations

"""
基于 Flask 的简易 Web 前端入口。

功能目标：
- 主页：系统概览导航
- 印刷任务：任务列表 + 新建任务表单（分页、可选CSRF/WTForms）
- 库存概览、库存预警
- 人员管理：列表分页、创建、编辑、删除（可选CSRF/WTForms）
"""

from datetime import datetime
from typing import Any, Dict, Optional
import os
import logging
from flask import Flask, render_template, request, redirect, url_for, flash, session

from src.config.settings import LOG_LEVEL, POSITIONS
from src.business_logic.service_factory import service_factory
from src.business_logic.user_service import UserService
from src.utils.auth import (
    login_required,
    admin_required,
    roles_required,
    get_current_user,
    is_admin,
    is_editor_or_admin,
    is_material_manager,
    is_inventory_operator,
)


def create_app() -> Flask:
    # 以项目根目录（printing_publisher_system）为基准配置模板和静态文件目录
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    templates_dir = os.path.join(base_dir, "templates")
    static_dir = os.path.join(base_dir, "static")

    app = Flask(
        __name__,
        template_folder=templates_dir,
        static_folder=static_dir,
    )
    # 从配置读取 secret_key（开发环境可走默认值，生产请通过环境变量设置）
    try:
        from src.config.settings import APP_SECRET_KEY
        app.secret_key = APP_SECRET_KEY
    except Exception:
        app.secret_key = "dev-secret-key-change-me"

    # 初始化日志
    logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO),
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")
    app.logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # 可选启用 CSRF 保护
    try:
        from flask_wtf import CSRFProtect  # type: ignore
        from flask_wtf.csrf import generate_csrf  # type: ignore
        CSRFProtect(app)
        app.jinja_env.globals['csrf_token'] = generate_csrf
    except Exception:
        app.logger.debug("Flask-WTF 未安装，CSRF 保护未启用")

    # 可选：定义 WTForms 表单
    NewTaskForm = None
    NewEmployeeForm = None
    EditEmployeeForm = None
    try:
        from flask_wtf import FlaskForm  # type: ignore
        from wtforms import IntegerField, DateField, StringField, SelectField  # type: ignore
        from wtforms.validators import DataRequired, NumberRange  # type: ignore

        class NewTaskForm(FlaskForm):  # type: ignore
            employee_id = IntegerField('员工id', validators=[DataRequired(), NumberRange(min=1)])
            book_id = IntegerField('书籍id', validators=[DataRequired(), NumberRange(min=1)])
            quantity = IntegerField('印刷数量', validators=[DataRequired(), NumberRange(min=1)])
            due_date = DateField('预计完成日期', validators=[DataRequired()], format='%Y-%m-%d')

        class NewEmployeeForm(FlaskForm):  # type: ignore
            name = StringField('员工姓名', validators=[DataRequired()])
            position = SelectField('职位', choices=[(p, p) for p in POSITIONS])
            status = SelectField('在职状态', choices=[('在职', '在职'), ('离职', '离职')], default='在职')
            hired_at = DateField('入职日期', format='%Y-%m-%d')

        class EditEmployeeForm(NewEmployeeForm):  # type: ignore
            pass
    except Exception:
        NewTaskForm = None
        NewEmployeeForm = None
        EditEmployeeForm = None

    # 服务实例
    printing_service = service_factory.get_printing_task_service()
    inventory_service = service_factory.get_inventory_service()
    employee_service = service_factory.get_employee_service()
    book_service = service_factory.get_book_service()
    material_supplier_service = service_factory.get_material_supplier_service()
    purchase_service = service_factory.get_purchase_service()
    user_service = UserService()

    # 在模板中注入当前用户信息
    @app.before_request
    def refresh_user_session():
        """
        每次请求前刷新 session 中的职位与用户名，保证权限实时生效。
        """
        if 'user_id' in session:
            user_info = user_service.get_user_by_id(session.get('user_id'))
            if user_info.get('success'):
                data = user_info.get('data', {})
                session['username'] = data.get('username')
                session['position'] = data.get('position')
            else:
                # 用户不存在或失效，清理会话
                session.clear()

    @app.context_processor
    def inject_user():
        return dict(
            current_user=get_current_user(),
            is_admin=is_admin(),
            is_editor_or_admin=is_editor_or_admin(),
            is_material_manager=is_material_manager(),
            is_inventory_operator=is_inventory_operator(),
        )

    # ========== 登录/登出 ==========
    @app.route("/login", methods=["GET", "POST"])
    def login():
        """登录页面"""
        # 如果已登录，重定向到首页
        if 'user_id' in session:
            return redirect(url_for('index'))
        
        if request.method == "POST":
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            
            result = user_service.authenticate(username, password)
            if result.get('success'):
                user_data = result.get('data', {})
                session['user_id'] = user_data.get('user_id')
                session['username'] = user_data.get('username')
                session['position'] = user_data.get('position')
                
                # 处理重定向
                next_url = request.args.get('next')
                if next_url:
                    return redirect(next_url)
                flash('登录成功', 'success')
                return redirect(url_for('index'))
            else:
                flash(result.get('message', '登录失败'), 'error')
        
        return render_template("login.html")

    @app.route("/logout")
    def logout():
        """登出"""
        session.clear()
        flash('已成功登出', 'success')
        return redirect(url_for('login'))

    # ========== 账号与密码 ==========
    @app.route("/account/password", methods=["GET", "POST"])
    @login_required
    def change_password():
        """用户自助修改密码"""
        if request.method == "POST":
            old_pwd = request.form.get("old_password", "")
            new_pwd = request.form.get("new_password", "")
            result = user_service.change_password(session.get("user_id"), old_pwd, new_pwd)
            if result.get("success"):
                flash("密码已更新，请重新登录", "success")
                return redirect(url_for("logout"))
            else:
                flash(result.get("message", "修改失败"), "error")
        return render_template("account/change_password.html")

    @app.route("/")
    @login_required
    def index():
        """系统首页，展示入口导航。"""
        return render_template("index.html")

    # ========== 印刷任务 ==========
    @app.route("/tasks", methods=["GET"])
    @login_required
    def list_tasks():
        """
        印刷任务列表页面，支持分页与状态过滤。
        查询参数：page, page_size, status
        """
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))
        except ValueError:
            page, page_size = 1, 10
        status = request.args.get("status") or None

        result = printing_service.list_tasks_page(page=page, page_size=page_size, status=status)
        if not result.get("success"):
            flash(result.get("message", "获取任务失败"), "error")
            page_data = {"items": [], "total": 0, "page": page, "page_size": page_size}
        else:
            page_data = result.get("data", {"items": [], "total": 0, "page": page, "page_size": page_size})

        total = int(page_data.get("total", 0))
        page = int(page_data.get("page", 1))
        page_size = int(page_data.get("page_size", 10))
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return render_template("tasks/list.html", page_data=page_data, status=status, total_pages=total_pages)

    @app.route("/tasks/new", methods=["GET", "POST"])
    @login_required
    def new_task():
        """
        新建印刷任务表单页面。提交后调用 PrintingTaskService.submit_printing_task。
        优先使用 WTForms 校验（若安装），否则回退原始校验。
        """
        default_due_date = (datetime.now().date().isoformat())

        # WTForms 路径
        if NewTaskForm is not None:
            form = NewTaskForm()
            if form.validate_on_submit():
                task_data: Dict[str, Any] = {
                    "员工id": int(form.employee_id.data),
                    "书籍id": int(form.book_id.data),
                    "印刷数量": int(form.quantity.data),
                    "预计完成日期": form.due_date.data.isoformat() if form.due_date.data else default_due_date,
                }
                result = printing_service.submit_printing_task(task_data)
                if result.get("success"):
                    flash(result.get("message", "任务提交成功"), "success")
                    return redirect(url_for("list_tasks"))
                else:
                    flash(result.get("message", "任务提交失败"), "error")
                    return redirect(url_for("new_task"))
            # GET 或校验失败
            return render_template("tasks/new.html", default_due_date=default_due_date, form=form)

        # 回退路径：无 WTForms
        if request.method == "POST":
            form = request.form
            try:
                task_data = {
                    "员工id": int(form.get("employee_id", "0") or 0),
                    "书籍id": int(form.get("book_id", "0") or 0),
                    "预计完成日期": form.get("due_date") or default_due_date,
                    "印刷数量": int(form.get("quantity", "0") or 0),
                }
            except ValueError:
                flash("表单数据格式错误，请检查输入。", "error")
                return redirect(url_for("new_task"))

            result = printing_service.submit_printing_task(task_data)
            if result.get("success"):
                flash(result.get("message", "任务提交成功"), "success")
                return redirect(url_for("list_tasks"))
            else:
                flash(result.get("message", "任务提交失败"), "error")
                return redirect(url_for("new_task"))

        # GET 请求
        return render_template("tasks/new.html", default_due_date=default_due_date)

    # ========== 任务：需求明细 & 手动完结 ==========
    @app.route("/tasks/<int:task_id>/requirements", methods=["GET"])
    @login_required
    def task_requirements(task_id: int):
        res = printing_service.get_task_requirements(task_id)
        if not res.get("success"):
            flash(res.get("message", "获取任务需求失败"), "error")
            return redirect(url_for("list_tasks"))
        data = res.get("data", {})
        task = data.get("task") or {}
        # 权限收紧：管理员/编辑/任务负责人可查看
        allow = is_editor_or_admin()
        if not allow:
            # 用与 inventory 相同的解析方式获取当前员工id
            op = None
            username = session.get("username")
            try:
                from src.database.daos import 员工DAO
                rows = 员工DAO().get_all(filters={"员工姓名": username}) if username else []
                if rows:
                    op = rows[0].get("员工id")
            except Exception:
                op = None
            allow = (op is not None and int(op) == int(task.get('员工id') or 0))
        if not allow:
            flash("您没有权限查看该任务的材料需求", "error")
            return redirect(url_for("list_tasks"))
        default_completed_date = datetime.now().date().isoformat()
        return render_template("tasks/requirements.html", task=task, items=data.get("items", []), default_completed_date=default_completed_date)

    @app.route("/tasks/<int:task_id>/complete", methods=["POST"])
    @login_required
    def task_complete_manual(task_id: int):
        # 权限收紧：管理员/编辑/任务负责人可提交完结
        res_ctx = printing_service.get_task_requirements(task_id)
        if not res_ctx.get("success"):
            flash(res_ctx.get("message", "获取任务失败"), "error")
            return redirect(url_for("list_tasks"))
        task = (res_ctx.get("data") or {}).get("task") or {}
        allow = is_editor_or_admin()
        if not allow:
            op_emp = None
            username = session.get("username")
            try:
                from src.database.daos import 员工DAO
                rows = 员工DAO().get_all(filters={"员工姓名": username}) if username else []
                if rows:
                    op_emp = rows[0].get("员工id")
            except Exception:
                op_emp = None
            allow = (op_emp is not None and int(op_emp) == int(task.get('员工id') or 0))
        if not allow:
            flash("您没有权限完成该任务", "error")
            return redirect(url_for("task_requirements", task_id=task_id))

        # 操作人优先取表单，其次按当前用户名在员工表匹配
        operator_id_raw = request.form.get("operator_employee_id")
        operator_id = None
        if operator_id_raw:
            try:
                operator_id = int(operator_id_raw)
            except Exception:
                operator_id = None
        if operator_id is None:
            username = session.get("username")
            try:
                from src.database.daos import 员工DAO
                emp_dao = 员工DAO()
                rows = emp_dao.get_all(filters={"员工姓名": username}) if username else []
                if rows:
                    operator_id = rows[0].get("员工id")
            except Exception:
                operator_id = None
        if operator_id is None:
            flash("无法确定操作人，请填写操作员工ID或创建与用户名同名的员工记录", "error")
            return redirect(url_for("task_requirements", task_id=task_id))
        completed_date = request.form.get("completed_date") or None
        res = printing_service.complete_task_manual(task_id, operator_id=int(operator_id), completed_date=completed_date)
        if not res.get("success"):
            # 若库存不足，跳回需求页查看缺口
            flash(res.get("message", "任务完成失败"), "error")
            return redirect(url_for("task_requirements", task_id=task_id))
        flash("任务已完成，材料已扣减", "success")
        return redirect(url_for("list_tasks"))

    # ========== 书籍与版本 ==========
    @app.route("/books", methods=["GET"])
    @login_required
    def books_list():
        name_kw = request.args.get("name") or None
        author = request.args.get("author") or None
        sort = request.args.get("sort") or None
        result = book_service.list_books(name_kw=name_kw, author=author, sort=sort)
        if not result.get("success"):
            flash(result.get("message", "获取书籍失败"), "error")
            items = []
        else:
            items = result.get("data", {}).get("items", [])
        return render_template("books/list.html", items=items, name=name_kw, author=author, sort=sort)

    @app.route("/books/new", methods=["GET", "POST"])
    @login_required
    @roles_required({"管理员", "编辑"})
    def books_new():
        if request.method == "POST":
            name = request.form.get("name", "")
            author = request.form.get("author", "")
            result = book_service.create_book(name, author)
            if result.get("success"):
                flash("书籍创建成功", "success")
                return redirect(url_for("books_list"))
            flash(result.get("message", "创建失败"), "error")
        return render_template("books/new.html")

    @app.route("/books/<int:book_id>/versions", methods=["GET"])
    @login_required
    def book_versions(book_id: int):
        # 获取书籍信息
        book_info = book_service.get_book(book_id)
        if not book_info.get("success"):
            flash(book_info.get("message", "书籍不存在"), "error")
            return redirect(url_for("books_list"))
        book = book_info.get("data", {})

        versions = book_service.list_versions(book_id)
        version_items = versions.get("data", {}).get("items", []) if versions.get("success") else []
        default_created_date = datetime.now().date().isoformat()
        return render_template("books/versions.html", book=book, versions=version_items, default_created_date=default_created_date)

    @app.route("/books/<int:book_id>/versions/new", methods=["POST"])
    @login_required
    @roles_required({"管理员", "编辑"})
    def book_versions_new(book_id: int):
        version_desc = request.form.get("version_desc", "")
        isbn = request.form.get("isbn", "")
        pages_raw = request.form.get("pages")
        format_text = request.form.get("format")
        created_date = request.form.get("created_date")
        pages = int(pages_raw) if pages_raw else None
        result = book_service.create_version(book_id, version_desc, isbn, pages, format_text, created_date)
        if result.get("success"):
            flash("版本创建成功", "success")
        else:
            flash(result.get("message", "创建失败"), "error")
        return redirect(url_for("book_versions", book_id=book_id))

    # ========== 材料与供应商 ==========
    @app.route("/materials", methods=["GET"])
    @login_required
    def materials_list():
        name_kw = request.args.get("name") or None
        result = material_supplier_service.list_materials(name_kw=name_kw)
        items = result.get("data", {}).get("items", []) if result.get("success") else []
        return render_template("materials/list.html", items=items, name=name_kw)

    @app.route("/materials/new", methods=["GET", "POST"])
    @login_required
    @roles_required({"管理员", "采购"})
    def materials_new():
        if request.method == "POST":
            name = request.form.get("name", "")
            unit = request.form.get("unit", "")
            spec = request.form.get("spec", "")
            price_raw = request.form.get("price", "")
            price = float(price_raw) if price_raw else None
            result = material_supplier_service.create_material(name, unit, spec, price)
            if result.get("success"):
                flash("材料创建成功", "success")
                return redirect(url_for("materials_list"))
            flash(result.get("message", "创建失败"), "error")
        return render_template("materials/new.html")

    @app.route("/suppliers", methods=["GET"])
    @login_required
    def suppliers_list():
        name_kw = request.args.get("name") or None
        status = request.args.get("status") or None
        result = material_supplier_service.list_suppliers(name_kw=name_kw, status=status)
        items = result.get("data", {}).get("items", []) if result.get("success") else []
        return render_template("suppliers/list.html", items=items, name=name_kw, status=status)

    @app.route("/suppliers/new", methods=["GET", "POST"])
    @login_required
    @roles_required({"管理员", "采购"})
    def suppliers_new():
        if request.method == "POST":
            name = request.form.get("name", "")
            contact = request.form.get("contact", "")
            phone = request.form.get("phone", "")
            status = request.form.get("status", "合作中")
            result = material_supplier_service.create_supplier(name, contact, phone, status)
            if result.get("success"):
                flash("供应商创建成功", "success")
                return redirect(url_for("suppliers_list"))
            flash(result.get("message", "创建失败"), "error")
        return render_template("suppliers/new.html")

    @app.route("/materials/<int:material_id>/suppliers", methods=["GET", "POST"])
    @login_required
    def material_suppliers(material_id: int):
        # 获取材料信息
        materials_result = material_supplier_service.list_materials()
        material = None
        if materials_result.get("success"):
            for m in materials_result.get("data", {}).get("items", []):
                if m.get("材料id") == material_id:
                    material = m
                    break
        if not material:
            flash("材料不存在", "error")
            return redirect(url_for("materials_list"))

        if request.method == "POST":
            if not is_material_manager():
                flash("您没有权限执行此操作", "error")
                return redirect(url_for("material_suppliers", material_id=material_id))
            supplier_id = int(request.form.get("supplier_id", "0") or 0)
            price_raw = request.form.get("price", "")
            preferred = request.form.get("preferred") == "on"
            price = float(price_raw) if price_raw else None
            result = material_supplier_service.create_material_supplier_link(material_id, supplier_id, price, preferred)
            if result.get("success"):
                flash("关联创建成功", "success")
            else:
                flash(result.get("message", "创建失败"), "error")
            return redirect(url_for("material_suppliers", material_id=material_id))

        links_result = material_supplier_service.list_material_suppliers(material_id)
        links = links_result.get("data", {}).get("items", []) if links_result.get("success") else []

        suppliers_result = material_supplier_service.list_suppliers()
        suppliers = suppliers_result.get("data", {}).get("items", []) if suppliers_result.get("success") else []

        return render_template(
            "materials/suppliers.html",
            material=material,
            links=links,
            suppliers=suppliers,
        )

    # ========== 人员管理 ==========
    @app.route("/employees", methods=["GET"])
    @login_required
    def employees_list():
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))
        except ValueError:
            page, page_size = 1, 10
        status = request.args.get("status") or None
        position = request.args.get("position") or None
        name_kw = request.args.get("name") or None

        result = employee_service.list_employees_page(page=page, page_size=page_size, status=status, position=position, name=name_kw)
        if not result.get("success"):
            flash(result.get("message", "获取员工失败"), "error")
            page_data = {"items": [], "total": 0, "page": page, "page_size": page_size}
        else:
            page_data = result.get("data", {"items": [], "total": 0, "page": page, "page_size": page_size})

        total = int(page_data.get("total", 0))
        page = int(page_data.get("page", 1))
        page_size = int(page_data.get("page_size", 10))
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0

        return render_template("employees/list.html", page_data=page_data, status=status, position=position, name=name_kw, positions=POSITIONS, total_pages=total_pages)

    @app.route("/employees/new", methods=["GET", "POST"])
    @login_required
    @admin_required
    def employees_new():
        # WTForms 路径
        if NewEmployeeForm is not None:
            form = NewEmployeeForm()
            if form.validate_on_submit():
                data = {
                    'name': (form.name.data or '').strip(),
                    'position': (form.position.data or '').strip(),
                    'status': form.status.data or '在职',
                    'hired_at': form.hired_at.data.isoformat() if getattr(form, 'hired_at', None) and form.hired_at.data else None,
                }
                result = employee_service.create_employee(data)
                if result.get('success'):
                    flash('员工创建成功', 'success')
                    return redirect(url_for('employees_list'))
                else:
                    flash(result.get('message', '创建失败'), 'error')
            return render_template('employees/new.html', form=form)

        # 回退路径
        if request.method == 'POST':
            form = request.form
            data = {
                'name': (form.get('name') or '').strip(),
                'position': (form.get('position') or '').strip(),
                'status': (form.get('status') or '在职').strip(),
            }
            result = employee_service.create_employee(data)
            if result.get('success'):
                flash('员工创建成功', 'success')
                return redirect(url_for('employees_list'))
            else:
                flash(result.get('message', '创建失败'), 'error')
        return render_template('employees/new.html', form=None)

    @app.route("/employees/<int:employee_id>/edit", methods=["GET", "POST"])
    @login_required
    @admin_required
    def employees_edit(employee_id: int):
        # 先获取员工信息
        info = employee_service.get_employee(employee_id)
        if not info.get('success'):
            flash(info.get('message', '员工不存在'), 'error')
            return redirect(url_for('employees_list'))
        row = info.get('data', {})

        if EditEmployeeForm is not None:
            form = EditEmployeeForm()
            if request.method == 'GET':
                form.name.data = row.get('员工姓名', '')
                form.position.data = row.get('职位', '')
                form.status.data = row.get('在职状态', '在职')
                return render_template('employees/edit.html', form=form, employee_id=employee_id, positions=POSITIONS)
            # POST
            if form.validate_on_submit():
                data = {
                    'name': (form.name.data or '').strip(),
                    'position': (form.position.data or '').strip(),
                    'status': form.status.data or '在职',
                }
                result = employee_service.update_employee(employee_id, data)
                if result.get('success'):
                    flash('员工已更新', 'success')
                    return redirect(url_for('employees_list'))
                flash(result.get('message', '更新失败'), 'error')
                return redirect(url_for('employees_edit', employee_id=employee_id))
            return render_template('employees/edit.html', form=form, employee_id=employee_id, positions=POSITIONS)

        # 回退路径：无 WTForms
        if request.method == 'POST':
            form = request.form
            data = {k: (form.get(k) or '').strip() for k in ('name', 'position', 'status')}
            result = employee_service.update_employee(employee_id, data)
            if result.get('success'):
                flash('员工已更新', 'success')
                return redirect(url_for('employees_list'))
            flash(result.get('message', '更新失败'), 'error')
            return redirect(url_for('employees_edit', employee_id=employee_id))
        # GET
        return render_template('employees/edit.html', form=None, employee=row, employee_id=employee_id, positions=POSITIONS)

    @app.route("/employees/<int:employee_id>/account", methods=["GET", "POST"])
    @login_required
    @admin_required
    def employees_account(employee_id: int):
        """
        管理员给员工设置初始账号和密码，或重置账号密码。
        """
        info = employee_service.get_employee(employee_id)
        if not info.get('success'):
            flash(info.get('message', '员工不存在'), 'error')
            return redirect(url_for('employees_list'))
        employee = info.get('data', {})
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = (request.form.get("password") or "").strip()
            if not username or not password:
                flash("用户名和密码不能为空", "error")
                return redirect(url_for("employees_account", employee_id=employee_id))
            position = employee.get('职位') or ''
            result = user_service.create_or_reset_user(username, password, position)
            if result.get("success"):
                flash(result.get("message", "账号已设置"), "success")
                return redirect(url_for("employees_list"))
            else:
                flash(result.get("message", "账号设置失败"), "error")
                return redirect(url_for("employees_account", employee_id=employee_id))
        suggested_username = (employee.get('员工姓名') or '').strip()
        return render_template("employees/account.html", employee=employee, suggested_username=suggested_username)

    @app.route("/employees/<int:employee_id>/delete", methods=["POST"])
    @login_required
    @admin_required
    def employees_delete(employee_id: int):
        result = employee_service.delete_employee(employee_id)
        if result.get('success'):
            flash('员工已删除', 'success')
        else:
            flash(result.get('message', '删除失败'), 'error')
        return redirect(url_for('employees_list'))

    # ========== 采购管理 ==========
    @app.route("/purchases", methods=["GET"])
    @login_required
    @roles_required({"管理员", "采购"})
    def purchases_list():
        try:
            page = int(request.args.get("page", 1))
            page_size = int(request.args.get("page_size", 10))
        except ValueError:
            page, page_size = 1, 10
        status = request.args.get("status") or None
        task_id = request.args.get("task_id") or None
        task_id_int = int(task_id) if task_id else None
        result = purchase_service.list_purchases_page(page=page, page_size=page_size, status=status, task_id=task_id_int)
        if not result.get("success"):
            flash(result.get("message", "获取采购记录失败"), "error")
            page_data = {"items": [], "total": 0, "page": page, "page_size": page_size}
        else:
            page_data = result.get("data", {"items": [], "total": 0, "page": page, "page_size": page_size})
        total = int(page_data.get("total", 0))
        page = int(page_data.get("page", 1))
        page_size = int(page_data.get("page_size", 10))
        total_pages = (total + page_size - 1) // page_size if page_size > 0 else 0
        return render_template("purchases/list.html", page_data=page_data, status=status, task_id=task_id, total_pages=total_pages)

    @app.route("/purchases/new", methods=["GET", "POST"])
    @login_required
    @roles_required({"管理员", "采购"})
    def purchases_new():
        if request.method == "POST":
            task_id = request.form.get("task_id")
            link_id = request.form.get("link_id")
            quantity = request.form.get("quantity")
            try:
                task_id_i = int(task_id or 0)
                link_id_i = int(link_id or 0)
                qty = float(quantity or 0)
            except Exception:
                flash("表单数据格式错误", "error")
                return redirect(url_for("purchases_new"))
            result = purchase_service.create_purchase(task_id_i, link_id_i, qty)
            if result.get("success"):
                flash("采购记录已创建", "success")
                return redirect(url_for("purchases_list"))
            else:
                flash(result.get("message", "创建失败"), "error")
                return redirect(url_for("purchases_new"))
        # GET: 获取材料-供应商关联用于选择
        links_res = purchase_service.list_all_links()
        links = links_res.get("data", {}).get("items", []) if links_res.get("success") else []
        return render_template("purchases/new.html", links=links)

    @app.route("/purchases/<int:purchase_id>/status", methods=["POST"])
    @login_required
    @roles_required({"管理员", "采购"})
    def purchases_update_status(purchase_id: int):
        new_status = request.form.get("status", "").strip()
        receipt_date = request.form.get("receipt_date") or None
        result = purchase_service.update_status(purchase_id, new_status, receipt_date)
        if result.get("success"):
            flash("采购状态已更新", "success")
        else:
            flash(result.get("message", "更新失败"), "error")
        return redirect(url_for("purchases_list"))

    @app.route("/purchases/<int:purchase_id>/receive", methods=["POST"])
    @login_required
    @roles_required({"管理员", "采购"})
    def purchases_receive(purchase_id: int):
        # 优先从表单获取操作员工ID，否则尝试用当前用户名匹配员工姓名
        operator_id_raw = request.form.get("operator_employee_id")
        operator_id: Optional[int] = None
        if operator_id_raw:
            try:
                operator_id = int(operator_id_raw)
            except Exception:
                operator_id = None
        if operator_id is None:
            # 尝试根据当前用户名找到员工ID
            username = session.get("username")
            try:
                from src.database.daos import 员工DAO  # 延迟导入避免循环
                emp_dao = 员工DAO()
                rows = emp_dao.get_all(filters={"员工姓名": username}) if username else []
                if rows:
                    operator_id = rows[0].get("员工id")
            except Exception:
                operator_id = None
        if operator_id is None:
            flash("无法确定操作人，请在表单中填写操作员工ID", "error")
            return redirect(url_for("purchases_list"))
        receipt_date = request.form.get("receipt_date") or None
        result = purchase_service.receive_purchase(purchase_id, operator_employee_id=operator_id, receipt_date=receipt_date)
        if result.get("success"):
            flash("收货并入库成功", "success")
        else:
            flash(result.get("message", "收货失败"), "error")
        return redirect(url_for("purchases_list"))

    # ========== 库存 ==========
    @app.route("/inventory", methods=["GET"])
    @login_required
    def inventory_overview():
        """
        库存总览页面。
        调用 InventoryService.get_inventory_report。
        """
        result = inventory_service.get_inventory_report()
        if result.get("success"):
            report = result.get("data", {})
        else:
            report = {}
            flash(result.get("message", "获取库存信息失败"), "error")

        return render_template("inventory/overview.html", report=report)

    @app.route("/inventory/alerts", methods=["GET"])
    @login_required
    def inventory_alerts():
        """
        库存预警列表页面。
        """
        result = inventory_service.check_low_stock_alerts()
        alerts: list[Dict[str, Any]] = []
        if result.get("success"):
            alerts = result.get("data", {}).get("alerts", [])
        else:
            flash(result.get("message", "获取库存预警失败"), "error")

        return render_template("inventory/alerts.html", alerts=alerts)

    # ========== 库存：材料列表与详情 ==========
    @app.route("/inventory/materials", methods=["GET"])
    @login_required
    def inventory_materials():
        name_kw = request.args.get("name") or None
        result = inventory_service.list_materials(name_kw=name_kw)
        items = result.get("data", {}).get("items", []) if result.get("success") else []
        return render_template("inventory/materials.html", items=items, name=name_kw)

    def _resolve_operator_id() -> Optional[int]:
        op: Optional[int] = None
        username = session.get("username")
        try:
            from src.database.daos import 员工DAO  # 延迟导入
            emp_dao = 员工DAO()
            rows = emp_dao.get_all(filters={"员工姓名": username}) if username else []
            if rows:
                op = rows[0].get("员工id")
        except Exception:
            op = None
        return op

    @app.route("/inventory/materials/<int:material_id>", methods=["GET"])
    @login_required
    def inventory_material_detail(material_id: int):
        res = inventory_service.get_material_detail(material_id, log_limit=100)
        if not res.get("success"):
            flash(res.get("message", "获取材料详情失败"), "error")
            return redirect(url_for("inventory_materials"))
        data = res.get("data", {})
        return render_template("inventory/detail.html", material=data.get("material"), logs=data.get("logs", []))

    @app.route("/inventory/materials/<int:material_id>/stock/in", methods=["POST"])
    @login_required
    @roles_required({"管理员", "采购", "仓储"})
    def inventory_stock_in(material_id: int):
        qty_raw = request.form.get("quantity", "")
        note = (request.form.get("note") or "").strip()
        try:
            qty = float(qty_raw)
            if qty <= 0:
                raise ValueError
        except Exception:
            flash("入库数量必须为正数", "error")
            return redirect(url_for("inventory_material_detail", material_id=material_id))
        op = _resolve_operator_id()
        if not op:
            flash("无法确定操作人，请先在员工表中创建与用户名同名的员工记录", "error")
            return redirect(url_for("inventory_material_detail", material_id=material_id))
        ref = f"manual_in:{material_id}:{int(datetime.now().timestamp())}"
        res = inventory_service.update_stock_level(material_id, change_quantity=qty, change_type="入库", reference_id=ref, operator_id=op, note=note)
        flash(res.get("message", "入库完成") if res.get("success") else res.get("message", "入库失败"), "success" if res.get("success") else "error")
        return redirect(url_for("inventory_material_detail", material_id=material_id))

    @app.route("/inventory/materials/<int:material_id>/stock/out", methods=["POST"])
    @login_required
    @roles_required({"管理员", "采购", "仓储"})
    def inventory_stock_out(material_id: int):
        qty_raw = request.form.get("quantity", "")
        note = (request.form.get("note") or "").strip()
        try:
            qty = float(qty_raw)
            if qty <= 0:
                raise ValueError
        except Exception:
            flash("出库数量必须为正数", "error")
            return redirect(url_for("inventory_material_detail", material_id=material_id))
        op = _resolve_operator_id()
        if not op:
            flash("无法确定操作人，请先在员工表中创建与用户名同名的员工记录", "error")
            return redirect(url_for("inventory_material_detail", material_id=material_id))
        ref = f"manual_out:{material_id}:{int(datetime.now().timestamp())}"
        res = inventory_service.update_stock_level(material_id, change_quantity=-qty, change_type="出库", reference_id=ref, operator_id=op, note=note)
        flash(res.get("message", "出库完成") if res.get("success") else res.get("message", "出库失败"), "success" if res.get("success") else "error")
        return redirect(url_for("inventory_material_detail", material_id=material_id))

    @app.route("/inventory/materials/<int:material_id>/stock/adjust", methods=["POST"])
    @login_required
    @roles_required({"管理员", "采购", "仓储"})
    def inventory_stock_adjust(material_id: int):
        qty_raw = request.form.get("delta", "")
        note = (request.form.get("note") or "").strip()
        try:
            delta = float(qty_raw)
            if delta == 0:
                raise ValueError
        except Exception:
            flash("调整数量必须为非0数字（可正可负）", "error")
            return redirect(url_for("inventory_material_detail", material_id=material_id))
        op = _resolve_operator_id()
        if not op:
            flash("无法确定操作人，请先在员工表中创建与用户名同名的员工记录", "error")
            return redirect(url_for("inventory_material_detail", material_id=material_id))
        ref = f"manual_adjust:{material_id}:{int(datetime.now().timestamp())}"
        res = inventory_service.update_stock_level(material_id, change_quantity=delta, change_type="调整", reference_id=ref, operator_id=op, note=note)
        flash(res.get("message", "调整完成") if res.get("success") else res.get("message", "调整失败"), "success" if res.get("success") else "error")
        return redirect(url_for("inventory_material_detail", material_id=material_id))

    @app.route("/inventory/materials/<int:material_id>/settings", methods=["POST"])
    @login_required
    @roles_required({"管理员", "采购", "仓储"})
    def inventory_material_settings(material_id: int):
        safety_raw = request.form.get("safety_stock")
        unit_price_raw = request.form.get("unit_price")
        if safety_raw is not None and safety_raw != "":
            try:
                safety = float(safety_raw)
            except Exception:
                flash("安全库存格式错误", "error")
                return redirect(url_for("inventory_material_detail", material_id=material_id))
            r = inventory_service.set_safety_stock(material_id, safety)
            if not r.get("success"):
                flash(r.get("message", "更新安全库存失败"), "error")
                return redirect(url_for("inventory_material_detail", material_id=material_id))
        if unit_price_raw is not None and unit_price_raw != "":
            try:
                unit_price = float(unit_price_raw)
            except Exception:
                flash("单价格式错误", "error")
                return redirect(url_for("inventory_material_detail", material_id=material_id))
            r = inventory_service.set_unit_price(material_id, unit_price)
            if not r.get("success"):
                flash(r.get("message", "更新标准单价失败"), "error")
                return redirect(url_for("inventory_material_detail", material_id=material_id))
        flash("已更新材料设置", "success")
        return redirect(url_for("inventory_material_detail", material_id=material_id))

    return app


if __name__ == "__main__":
    from src.config.settings import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
    app = create_app()
    # 开发模式启动，生产环境请使用专业 WSGI/ASGI 服务器
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)
