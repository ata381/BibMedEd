"""Records the JSON shape of every analysis endpoint for the frontend e2e mocks.

The Playwright mocks in ``frontend/e2e/mock-api.ts`` are checked against
``frontend/e2e/fixtures/api-shapes.json`` by ``frontend/e2e/api-contract.spec.ts``.
This test keeps that fixture honest: it seeds the bundled sample project, calls
each analysis endpoint and compares the observed shapes with the checked-in file.

Refresh after an intentional response change with::

    UPDATE_API_SHAPES=1 pytest tests/test_api_shapes_contract.py
"""

import json
import os
from pathlib import Path

import pytest

from bibmeded.analysis import ANALYSIS_FUNCTIONS

SHAPES_PATH = Path(__file__).resolve().parents[1] / "frontend" / "e2e" / "fixtures" / "api-shapes.json"
UPDATE_ENV_VAR = "UPDATE_API_SHAPES"

# The sample corpus never produces null at these paths, but the analysis code can
# (missing year, missing ORCID, undefined growth from a zero year, failed logistic
# fit). Declaring them keeps the fixture from claiming a field is never null just
# because the sample data happens to fill it.
KNOWN_NULLABLE: dict[str, dict[str, str]] = {
    "publications": {
        "results.field_maturity": "object",
        "results.growth_rates[].rate": "number",
    },
    "authors": {
        "results.top_authors[].orcid": "string",
    },
    "citations": {
        "results.most_cited[].year": "number",
        "results.citation_network.nodes[].year": "number",
        "results.coupling_network.nodes[].year": "number",
        "results.cocitation_network.nodes[].year": "number",
    },
}


def shape_of(value, path: str = "$") -> dict:
    if value is None:
        return {"type": "null"}
    if isinstance(value, bool):
        return {"type": "boolean"}
    if isinstance(value, (int, float)):
        return {"type": "number"}
    if isinstance(value, str):
        return {"type": "string"}
    if isinstance(value, list):
        items = None
        for element in value:
            element_shape = shape_of(element, f"{path}[]")
            items = element_shape if items is None else merge_shapes(items, element_shape, f"{path}[]")
        return {"type": "array", "items": items}
    if isinstance(value, dict):
        return {
            "type": "object",
            "properties": {key: shape_of(value[key], f"{path}.{key}") for key in sorted(value)},
        }
    raise TypeError(f"{path}: unsupported JSON value of type {type(value).__name__}")


def merge_shapes(a: dict, b: dict, path: str) -> dict:
    if a["type"] == "null" and b["type"] == "null":
        return a
    if a["type"] == "null":
        return {**b, "nullable": True}
    if b["type"] == "null":
        return {**a, "nullable": True}
    if a["type"] != b["type"]:
        raise ValueError(f"{path}: list elements mix {a['type']} and {b['type']}")

    merged = {"type": a["type"]}
    if a.get("nullable") or b.get("nullable"):
        merged["nullable"] = True
    if a["type"] == "array":
        if a["items"] is None or b["items"] is None:
            merged["items"] = a["items"] or b["items"]
        else:
            merged["items"] = merge_shapes(a["items"], b["items"], f"{path}[]")
    elif a["type"] == "object":
        properties = {}
        for key in sorted(a["properties"].keys() | b["properties"].keys()):
            left, right = a["properties"].get(key), b["properties"].get(key)
            if left is None or right is None:
                properties[key] = {**(left or right), "optional": True}
            else:
                properties[key] = merge_shapes(left, right, f"{path}.{key}")
        merged["properties"] = properties
    return merged


def _node_at(shape: dict, path: str) -> dict:
    node = shape
    for segment in path.split("."):
        is_list = segment.endswith("[]")
        key = segment[:-2] if is_list else segment
        properties = node.get("properties")
        if properties is None or key not in properties:
            raise KeyError(f"declared nullable path {path!r} does not exist in the response")
        node = properties[key]
        if is_list:
            if node.get("items") is None:
                raise KeyError(f"declared nullable path {path!r} crosses an empty list")
            node = node["items"]
    return node


def mark_nullable(shape: dict, declared: dict[str, str]) -> None:
    for path, expected_type in declared.items():
        node = _node_at(shape, path)
        if node["type"] == "null":
            node["type"] = expected_type
        elif node["type"] != expected_type:
            raise AssertionError(f"{path}: declared {expected_type} but backend returned {node['type']}")
        node["nullable"] = True


def collect_api_shapes(client) -> dict:
    created = client.post("/api/projects/sample")
    assert created.status_code in (200, 201), created.text
    project_id = created.json()["id"]

    shapes = {}
    for analysis_type in sorted(ANALYSIS_FUNCTIONS):
        url = f"/api/projects/{project_id}/analysis/{analysis_type}"
        ran = client.post(url)
        assert ran.status_code == 200, ran.text
        cached = client.get(url)
        assert cached.status_code == 200, cached.text
        shape = shape_of(cached.json())
        assert shape == shape_of(ran.json()), f"{analysis_type}: GET and POST responses differ in shape"
        mark_nullable(shape, KNOWN_NULLABLE.get(analysis_type, {}))
        shapes[analysis_type] = shape
    return shapes


def render(shapes: dict) -> str:
    return json.dumps(shapes, indent=2, sort_keys=True) + "\n"


def test_shape_of_merges_list_elements_and_marks_optional_and_nullable_keys():
    shape = shape_of([{"a": 1, "b": None}, {"a": 2, "b": "x", "c": True}])

    assert shape == {
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "a": {"type": "number"},
                "b": {"type": "string", "nullable": True},
                "c": {"type": "boolean", "optional": True},
            },
        },
    }


def test_shape_of_leaves_empty_list_items_unknown():
    assert shape_of({"xs": []}) == {"type": "object", "properties": {"xs": {"type": "array", "items": None}}}


def test_mark_nullable_rejects_paths_the_backend_does_not_return():
    shape = shape_of({"results": {"a": 1}})

    with pytest.raises(KeyError, match="results.missing"):
        mark_nullable(shape, {"results.missing": "number"})


def test_api_shapes_fixture_matches_backend(client):
    rendered = render(collect_api_shapes(client))

    if os.environ.get(UPDATE_ENV_VAR) == "1":
        SHAPES_PATH.parent.mkdir(parents=True, exist_ok=True)
        SHAPES_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        return

    assert SHAPES_PATH.exists(), (
        f"{SHAPES_PATH} is missing. Generate it with: {UPDATE_ENV_VAR}=1 pytest tests/test_api_shapes_contract.py"
    )
    checked_in = SHAPES_PATH.read_text(encoding="utf-8")
    assert json.loads(checked_in) == json.loads(rendered), (
        f"{SHAPES_PATH.name} is stale: an analysis response shape changed. Refresh it with "
        f"`{UPDATE_ENV_VAR}=1 pytest tests/test_api_shapes_contract.py`, then update "
        "frontend/e2e/mock-api.ts until `npx playwright test api-contract` passes."
    )
