"""CQL datetime-precision-aware wrappers.

A full CQL engine needs precision-carrying Date / DateTime / Time types. For
the scaffold we re-export ``datetime`` primitives with a thin alias so later
work has a single module to extend.
"""

from __future__ import annotations

from datetime import date as CqlDate
from datetime import datetime as CqlDateTime
from datetime import time as CqlTime
from datetime import timezone as CqlTimezone

__all__ = ["CqlDate", "CqlDateTime", "CqlTime", "CqlTimezone"]
