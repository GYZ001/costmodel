"""Language-neutral messages.

Every sentence the website shows about the data (why a figure was left out, what a
wage measures, how it was converted) is published as a message: a key and its
parameters, {"k": key, "p": {...}}.  The website renders it in the reader's language
from its catalogs (web/src/i18n/locales/*.json), where each key has one template per
language, e.g. "ILOSTAT 注明该值为“{label}”…" with "{label}" filled in.

Parameter values:
- number: formatted by the template ("{v:num}", "{r:factor}", "{p:pct2}", …)
- str: inserted as is - codes, years, and text quoted verbatim from a publisher
  (ILOSTAT's English note labels and survey names)
- message: rendered in the same language
- list: each item rendered, joined with the language's list separator
"""
from __future__ import annotations

import json
from typing import Any, Union

Msg = dict
Part = Union[Msg, str, list]


def M(key: str, **params: Any) -> Msg:
    return {"k": key, "p": params} if params else {"k": key}


def key_of(part: Part | None) -> str | None:
    return part.get("k") if isinstance(part, dict) else None


def canonical(part: Part) -> str:
    """A stable text form, for de-duplicating and sorting messages."""
    return json.dumps(part, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
