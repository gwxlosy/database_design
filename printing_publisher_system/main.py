from src.web_app import create_app

"""
应用入口：
- Web 版通过 Flask 在此启动
- 桌面版如需开发，可继续在 src/user_interface 中扩展
"""


if __name__ == "__main__":
    from src.config.settings import FLASK_HOST, FLASK_PORT, FLASK_DEBUG
    app = create_app()
    app.run(host=FLASK_HOST, port=FLASK_PORT, debug=FLASK_DEBUG)


