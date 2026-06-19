from enum import Enum


class PhysicsMode(str, Enum):
    none = 'none'
    observer = 'observer'
    controller = 'controller'
