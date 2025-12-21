"""Custom SQLAlchemy Mutable types with hashing support."""

from sqlalchemy.ext.mutable import MutableDict, MutableList, MutableSet

from sqlatypemodel.mixin.serialization import ForceHashMixin


class KeyableMutableList(ForceHashMixin, MutableList):
    pass


class KeyableMutableDict(ForceHashMixin, MutableDict):
    pass

class KeyableMutableSet(ForceHashMixin, MutableSet):
    pass
