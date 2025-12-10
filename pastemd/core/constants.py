"""Application constants."""

from enum import Enum


class NoAppAction(str, Enum):
    """无应用检测时的动作类型"""
    OPEN = "open"
    SAVE = "save"
    CLIPBOARD = "clipboard"
    NONE = "none"


def get_no_app_action_choices() -> list[str]:
    """返回所有可用的动作值列表"""
    return [action.value for action in NoAppAction]


# 触发防抖时间（秒）
FIRE_DEBOUNCE_SEC = 0.5

# 重试相关
WORD_INSERT_RETRY_COUNT = 3
WORD_INSERT_RETRY_DELAY = 0.3  # 秒

# 默认通知超时时间
NOTIFICATION_TIMEOUT = 3

# 清理等待时间
CLEANUP_DELAY = 1.0  # 秒

# 缓存删除相关
DEFAULT_DELETE_RETRY = 3
DEFAULT_DELETE_WAIT  = 0.05
