# -*- coding: utf-8 -*-
"""Base classes for paste-based content placement."""

from abc import ABC, abstractmethod
from ...core.types import PlacementResult


class BasePastePlacer(ABC):
    """粘贴落地器基类

    统一抽象"设置剪贴板 + 模拟粘贴"的模式。
    适用于不支持直接自动化 API，但接受标准粘贴操作的应用程序。
    """

    @abstractmethod
    def place(self, content: str, config: dict, **kwargs) -> PlacementResult:
        """
        将内容设置到剪贴板并模拟粘贴

        Args:
            content: 要粘贴的内容（纯文本）
            config: 配置字典
            **kwargs: 额外参数（如 html、rtf_bytes 等）

        Returns:
            PlacementResult: 落地结果
        """
        pass
