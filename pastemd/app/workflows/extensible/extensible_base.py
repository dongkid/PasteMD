# -*- coding: utf-8 -*-
"""Extensible workflow base class."""

from abc import abstractmethod
from ..base import BaseWorkflow
from ....core.state import app_state


class ExtensibleWorkflow(BaseWorkflow):
    """可扩展工作流基类
    
    用于用户可配置的工作流，例如针对特定应用的粘贴行为。
    子类需要实现 workflow_key 属性和 execute 方法。
    """
    
    @property
    @abstractmethod
    def workflow_key(self) -> str:
        """配置中的工作流键名，如 'html_md'"""
        ...
    
    @property
    def workflow_config(self) -> dict:
        """获取此工作流的配置"""
        ext_config = self.config.get("extensible_workflows", {})
        return ext_config.get(self.workflow_key, {})
    
    @property
    def enabled(self) -> bool:
        """检查此工作流是否启用"""
        return self.workflow_config.get("enabled", False)
    
    @property
    def enabled_apps(self) -> list[str]:
        """获取此工作流启用的应用名称列表"""
        apps = self.workflow_config.get("apps", [])
        # apps 是 [{"name": ..., "path": ...}, ...] 格式
        return [app["name"] for app in apps if isinstance(app, dict)]
