# src/utils/data_utils.py
import datetime
from typing import Union

def safe_date_conversion(date_input: Union[str, datetime.date], format_str: str = '%Y-%m-%d') -> datetime.date:
    """安全地将输入转换为日期对象"""
    if isinstance(date_input, datetime.date):
        return date_input
    elif isinstance(date_input, str):
        try:
            return datetime.datetime.strptime(date_input, format_str).date()
        except ValueError:
            raise ValueError(f"日期格式错误，期望格式: {format_str}")
    else:
        raise TypeError("输入必须是字符串或日期对象")