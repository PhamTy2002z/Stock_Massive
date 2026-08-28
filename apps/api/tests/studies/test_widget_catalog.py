"""The published catalog and the code that generates it, held equal.

``contracts/signal-desk-widget-catalog.json`` is what the browser reads: it is a
generated file, and the only thing that makes a generated file trustworthy is a
test that fails when someone edits the source and forgets to regenerate — or
edits the JSON by hand. Regenerate with::

    python -c "import json;from src.studies import widgets;\
print(json.dumps(widgets.catalog_payload(),ensure_ascii=False,indent=2))" \
      > ../../contracts/signal-desk-widget-catalog.json

The path is resolved from this file rather than from the working directory: the
suite runs from ``apps/api`` and the contract lives at the repository root,
because two apps read it.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.studies import widgets

CATALOG_JSON = (
    Path(__file__).resolve().parents[4] / "contracts" / "signal-desk-widget-catalog.json"
)


def published() -> dict:
    return json.loads(CATALOG_JSON.read_text(encoding="utf-8"))


def test_the_published_catalog_is_the_one_the_code_generates():
    assert published() == widgets.catalog_payload()


def test_the_fallback_widget_is_published_and_draws_every_frame_kind():
    payload = published()
    fallback = payload["fallback"]

    assert (fallback["widget"], fallback["version"]) == widgets.FALLBACK_WIDGET
    entry = next(
        item
        for item in payload["widgets"]
        if (item["name"], item["version"]) == widgets.FALLBACK_WIDGET
    )
    assert set(entry["frameKinds"]) == {"series", "matrix", "table"}


def test_every_published_widget_is_a_widget_the_registry_will_admit():
    for item in published()["widgets"]:
        assert widgets.known(item["name"], item["version"])
