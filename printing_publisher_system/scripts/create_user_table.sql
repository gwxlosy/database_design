-- 创建用户表
-- 用于存储系统登录用户的账户和密码信息
-- 设置字符集
SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS 用户表 (
    用户id INT AUTO_INCREMENT PRIMARY KEY COMMENT '用户ID，主键',
    用户名 VARCHAR(50) NOT NULL UNIQUE COMMENT '登录用户名，唯一',
    密码 VARCHAR(255) NOT NULL COMMENT '密码（SHA256哈希值）',
    职位 VARCHAR(20) NOT NULL COMMENT '用户职位（编辑、排版、印刷工、采购、仓储、销售、人事、管理员等）',
    创建时间 DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '账户创建时间',
    INDEX idx_username (用户名),
    INDEX idx_position (职位)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统用户表';

-- 插入默认管理员账户（用户名：admin，密码：admin123）
-- 注意：密码是 'admin123' 的 SHA256 哈希值
INSERT INTO 用户表 (用户名, 密码, 职位) 
VALUES ('admin', '240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9', '管理员')
ON DUPLICATE KEY UPDATE 用户名=用户名;

-- 说明：
-- 1. 用户表包含：用户ID、用户名、密码（哈希值）、职位、创建时间
-- 2. 用户名必须唯一
-- 3. 密码使用SHA256哈希存储（生产环境建议使用bcrypt）
-- 4. 职位字段用于权限控制，只有"管理员"可以修改员工表
-- 5. 默认管理员账户：用户名 admin，密码 admin123
-- 6. 如需创建其他用户，可以使用以下SQL：
--    INSERT INTO 用户表 (用户名, 密码, 职位) VALUES ('用户名', '密码的SHA256哈希值', '职位');

