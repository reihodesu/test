"""
Core Package for Battery Calculator V3
=======================================

共通基盤レイヤー: 設定, パラメータ管理, 例外定義。

Modules:
    - config: パス管理, AgingConstants
    - param_loader_design: CSV 読込, P() SSoT ハブ
    - exceptions: 統一例外階層 (CalcError 基底)
"""

__version__ = "5.0.0"

from .exceptions import (
    CalcError,
    ConfigError,
    DataError,
    DomainError,
    ParameterNotFoundError,
    InvalidParameterError,
)

# 後方互換
from .exceptions import AgingCalcError

__all__ = [
    "CalcError",
    "ConfigError",
    "DataError",
    "DomainError",
    "ParameterNotFoundError",
    "InvalidParameterError",
    "AgingCalcError",
]
