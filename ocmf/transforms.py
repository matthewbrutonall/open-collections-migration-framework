"""Closed-vocabulary field transforms shared by all adapters.

Every transform declared in ``VALID_TRANSFORMS`` must be handled by
``apply_transform`` — the compiler validates workbooks against this exact set,
so a transform that validates but is not implemented here would crash mid-run.
Keep the two in lockstep.
"""

import re
from typing import Optional, Any

from ocmf.kernel.models import DateValue

VALID_TRANSFORMS = {'identity', 'split', 'parse_date', 'lookup'}


def _parse_lookup_args(args: Optional[str]) -> dict:
    """Parse ``"k1=v1;k2=v2"`` into a lookup dict."""
    mapping = {}
    if not args:
        return mapping
    for pair in str(args).split(';'):
        pair = pair.strip()
        if not pair or '=' not in pair:
            continue
        key, value = pair.split('=', 1)
        mapping[key.strip()] = value.strip()
    return mapping


def apply_transform(val: Any, transform: str, args: Optional[str] = None) -> Any:
    """Apply a closed-vocabulary transform to a single source value.

    - ``identity``   : trimmed string, unchanged.
    - ``split``      : split on ``args`` (delimiter, default ``;``) and re-join
                       with ``|`` so downstream parallel-array logic sees one
                       normalised multi-value field.
    - ``lookup``     : map the value via ``args`` (``"k1=v1;k2=v2"``); values
                       with no matching key pass through unchanged.
    - ``parse_date`` : produce a :class:`DateValue`, preserving uncertainty by
                       leaving ``begin``/``end`` unset for non-standard input.
    """
    if not val:
        return ""
    val = str(val).strip()

    if transform == 'identity':
        return val

    if transform == 'split':
        delimiter = args if args else ';'
        parts = [p.strip() for p in val.split(delimiter) if p.strip()]
        return "|".join(parts)

    if transform == 'lookup':
        mapping = _parse_lookup_args(args)
        return mapping.get(val, val)

    if transform == 'parse_date':
        m_year = re.match(r'^\s*(\d{4})\s*$', val)
        if m_year:
            return DateValue(expression=val, begin=m_year.group(1), end=m_year.group(1))

        m_range = re.match(r'^\s*(\d{4})\s*-\s*(\d{4})\s*$', val)
        if m_range:
            return DateValue(expression=val, begin=m_range.group(1), end=m_range.group(2))

        return DateValue(expression=val, begin=None, end=None)

    # Defensive: a transform passed workbook validation but is unhandled here.
    raise NotImplementedError(f"Transform '{transform}' is not implemented.")
