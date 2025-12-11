"""
创建用户账户的辅助脚本
用于快速创建新用户账户
"""
import sys
import os
import hashlib

# 添加项目根目录到路径
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

from src.business_logic.user_service import UserService


def hash_password(password: str) -> str:
    """计算密码的SHA256哈希值"""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()


def create_user():
    """交互式创建用户"""
    print("=" * 50)
    print("创建新用户账户")
    print("=" * 50)
    
    username = input("请输入用户名: ").strip()
    if not username:
        print("❌ 用户名不能为空")
        return
    
    password = input("请输入密码: ").strip()
    if not password:
        print("❌ 密码不能为空")
        return
    
    print("\n可选职位：")
    positions = ['编辑', '排版', '印刷工', '采购', '仓储', '销售', '人事', '管理员']
    for i, pos in enumerate(positions, 1):
        print(f"  {i}. {pos}")
    
    position_input = input("\n请输入职位（输入序号或职位名称）: ").strip()
    
    # 尝试解析为序号
    try:
        pos_index = int(position_input) - 1
        if 0 <= pos_index < len(positions):
            position = positions[pos_index]
        else:
            print("❌ 无效的序号")
            return
    except ValueError:
        # 不是序号，当作职位名称
        if position_input in positions:
            position = position_input
        else:
            print("❌ 无效的职位名称")
            return
    
    # 创建用户
    user_service = UserService()
    result = user_service.create_user(username, password, position)
    
    if result.get('success'):
        print(f"\n✅ 用户创建成功！")
        print(f"   用户名: {username}")
        print(f"   职位: {position}")
        print(f"   用户ID: {result.get('data', {}).get('user_id')}")
    else:
        print(f"\n❌ 创建失败: {result.get('message')}")


if __name__ == '__main__':
    try:
        create_user()
    except KeyboardInterrupt:
        print("\n\n操作已取消")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

