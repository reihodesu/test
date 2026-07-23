"""
Exception Classes for Battery Calculator V3
=============================================

統一例外階層:
    CalcError (base)
    ├── ConfigError          … 設定・ファイル不在
    ├── DataError            … 入力データ不正
    ├── DomainError          … 物理的に解なし (判別式負 等)
    ├── ParameterNotFoundError … パラメータ未登録
    └── InvalidParameterError  … パラメータ値不正
"""


class CalcError(Exception):
    """Base exception for all calculation errors."""
    pass


class ConfigError(CalcError):
    """Configuration or file not found error (fatal)."""
    pass


class DataError(CalcError):
    """Input data validation error (potentially recoverable)."""
    pass


class DomainError(CalcError, ValueError):
    """物理的に解なし（判別式負 等）。ValueError 互換。"""
    pass


class ParameterNotFoundError(CalcError):
    """指定パラメータが CSV に存在しない。"""
    def __init__(self, name: str, source: str = ""):
        self.name = name
        self.source = source
        super().__init__(f"Parameter '{name}' not found in {source}")


class InvalidParameterError(CalcError):
    """パラメータ値が不正（NaN / Inf 等）。"""
    def __init__(self, name: str, value, reason: str = ""):
        self.name = name
        self.value = value
        super().__init__(f"Invalid parameter '{name}'={value}: {reason}")


# 後方互換エイリアス
AgingCalcError = CalcError
NegativeDiscriminantError = DomainError


__all__ = [
    "CalcError",
    "ConfigError",
    "DataError",
    "DomainError",
    "ParameterNotFoundError",
    "InvalidParameterError",
    # 後方互換
    "AgingCalcError",
    "NegativeDiscriminantError",
]
