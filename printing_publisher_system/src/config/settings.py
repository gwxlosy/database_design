import os

# 可选加载 .env（如果已安装 python-dotenv）
try:
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()  # 在项目根目录放置 .env 可自动加载
except Exception:
    pass

# 环境读取工具
def getenv_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}

# 数据库配置（从环境变量读取，提供安全默认值）
DB_CONFIG = {
    'host': os.getenv('DB_HOST', '10.82.157.204'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', '123456'),
    'database': os.getenv('DB_NAME', 'printing_publisher_db'),
    'charset': os.getenv('DB_CHARSET', 'utf8mb4'),
    'connect_timeout': int(os.getenv('DB_CONNECT_TIMEOUT', '10')),
}

# 应用配置
APP_CONFIG = {
    'title': os.getenv('APP_TITLE', '印刷出版商数据库管理系统'),
    'version': os.getenv('APP_VERSION', '1.0.0'),
    'window_size': os.getenv('APP_WINDOW_SIZE', '1200x700'),
}

# Flask/应用通用配置
APP_SECRET_KEY = os.getenv('APP_SECRET_KEY', 'dev-secret-key-change-me')
FLASK_DEBUG = getenv_bool('FLASK_DEBUG', True)
FLASK_HOST = os.getenv('FLASK_HOST', '127.0.0.1')
FLASK_PORT = int(os.getenv('FLASK_PORT', '5000'))
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()

# 职位白名单（可通过环境变量 POSITIONS 覆盖，使用中文逗号或英文逗号分隔）
# 默认去掉仓储、排版、销售
_raw_positions = os.getenv('POSITIONS', '编辑,印刷工,采购,人事,管理员')
POSITIONS = [p.strip() for p in _raw_positions.replace('，', ',').split(',') if p.strip()]