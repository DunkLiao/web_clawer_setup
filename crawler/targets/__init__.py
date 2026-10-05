"""目標套件。

匯入各目標模組以觸發 `@register`，讓目標名稱能對應到 Python 類別。
新增目標時，若只是 YAML 設定就不必動這裡；若有對應的 .py，請在此匯入。
"""
from crawler.targets.base import BaseTarget, register, registered
from crawler.targets import example  # noqa: F401  （觸發 ExampleTarget 註冊）

__all__ = ["BaseTarget", "register", "registered"]
