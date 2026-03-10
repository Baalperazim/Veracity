from enum import Enum

try:
    from enum import StrEnum as NativeStrEnum
except ImportError:
    class NativeStrEnum(str, Enum):
        pass


StrEnum = NativeStrEnum
