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
from collections import Counter
from pathlib import Path

import pytest

from bibmeded.analysis import ANALYSIS_FUNCTIONS
from bibmeded.analysis.citations import analyze_citations
from bibmeded.analysis.keywords import _detect_bursts
from bibmeded.models import Publication
from bibmeded.models.citation import Citation

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
        "results.growth_summary.cagr": "number",
        "results.growth_summary.doubling_time_years": "number",
        "results.growth_summary.reason": "string",
        "results.growth_summary.start_year": "number",
        "results.growth_summary.end_year": "number",
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
SCALAR_TYPES = {"boolean", "number", "string"}

_NUMBER = {"type": "number"}

# Lists the sample corpus leaves empty: it has no Citation rows and is too small
# for a keyword burst. test_known_items_match_backend_output proves these against
# the real code paths so they cannot silently drift from the backend.
KNOWN_ITEMS: dict[str, dict[str, dict]] = {
    "citations": {
        "results.citation_network.links": {
            "type": "object",
            "properties": {"source": _NUMBER, "target": _NUMBER},
        },
    },
    "keywords": {
        "results.burst_terms": {
            "type": "object",
            "properties": {
                "baseline_share": _NUMBER,
                "count": _NUMBER,
                "intensity": _NUMBER,
                "term": {"type": "string"},
                "year": _NUMBER,
            },
        },
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
            raise KeyError(f"declared path {path!r} does not exist in the response")
        node = properties[key]
        if is_list:
            if node.get("items") is None:
                raise KeyError(f"declared path {path!r} crosses an empty list")
            node = node["items"]
    return node


def mark_nullable(shape: dict, declared: dict[str, str]) -> None:
    for path, expected_type in declared.items():
        node = _node_at(shape, path)
        if node["type"] == "null":
            if expected_type not in SCALAR_TYPES:
                raise ValueError(
                    f"{path}: the sample data only returns null, so the {expected_type} structure is unknown"
                )
            node["type"] = expected_type
        elif node["type"] != expected_type:
            raise AssertionError(f"{path}: declared {expected_type} but backend returned {node['type']}")
        node["nullable"] = True


def apply_known_items(shape: dict, declared: dict[str, dict]) -> None:
    for path, element_shape in declared.items():
        node = _node_at(shape, path)
        if node["type"] != "array":
            raise AssertionError(f"{path}: declared list items but backend returned {node['type']}")
        if node["items"] is None:
            node["items"] = element_shape
            continue
        drift = diff_shapes(element_shape, node["items"], f"{path}[]")
        assert not drift, "KNOWN_ITEMS is out of date:\n" + "\n".join(drift)


def unresolved_paths(shape: dict | None, path: str = "$") -> list[str]:
    if shape is None:
        return [f"{path}: list is empty in the sample data; declare its element shape in KNOWN_ITEMS"]
    if shape["type"] == "null":
        return [f"{path}: only null in the sample data; declare its type in KNOWN_NULLABLE"]
    if shape["type"] == "array":
        return unresolved_paths(shape["items"], f"{path}[]")
    if shape["type"] == "object":
        return [
            problem
            for key, child in shape["properties"].items()
            for problem in unresolved_paths(child, f"{path}.{key}")
        ]
    return []


def _describe(shape: dict | None) -> str:
    if shape is None:
        return "unknown"
    text = shape["type"]
    if shape.get("nullable"):
        text += " | null"
    if shape.get("optional"):
        text += " (optional)"
    return text


def diff_shapes(expected: dict | None, actual: dict | None, path: str = "$") -> list[str]:
    if expected is None or actual is None:
        if expected is None and actual is None:
            return []
        return [f"changed {path}: {_describe(expected)} -> {_describe(actual)}"]
    if (expected["type"], expected.get("nullable"), expected.get("optional")) != (
        actual["type"],
        actual.get("nullable"),
        actual.get("optional"),
    ):
        return [f"changed {path}: {_describe(expected)} -> {_describe(actual)}"]
    if expected["type"] == "array":
        return diff_shapes(expected["items"], actual["items"], f"{path}[]")
    if expected["type"] != "object":
        return []
    drift = []
    old, new = expected["properties"], actual["properties"]
    for key in sorted(old.keys() | new.keys()):
        child_path = f"{path}.{key}"
        if key not in new:
            drift.append(f"removed {child_path} (was {_describe(old[key])})")
        elif key not in old:
            drift.append(f"added {child_path} ({_describe(new[key])})")
        else:
            drift.extend(diff_shapes(old[key], new[key], child_path))
    return drift


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
        apply_known_items(shape, KNOWN_ITEMS.get(analysis_type, {}))
        unresolved = unresolved_paths(shape, analysis_type)
        assert not unresolved, "\n".join(unresolved)
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


def test_mark_nullable_types_a_sample_null_scalar_from_the_declaration():
    shape = shape_of({"results": {"doubling_time_years": None}})

    mark_nullable(shape, {"results.doubling_time_years": "number"})

    assert _node_at(shape, "results.doubling_time_years") == {"type": "number", "nullable": True}
    assert unresolved_paths(shape) == []


def test_mark_nullable_refuses_to_guess_the_structure_of_a_sample_null_object():
    shape = shape_of({"results": {"field_maturity": None}})

    with pytest.raises(ValueError, match="results.field_maturity"):
        mark_nullable(shape, {"results.field_maturity": "object"})


def test_unresolved_paths_flags_undeclared_nulls_and_empty_lists():
    shape = shape_of({"results": {"reason": None, "bursts": []}})

    assert unresolved_paths(shape, "keywords") == [
        "keywords.results.bursts[]: list is empty in the sample data; declare its element shape in KNOWN_ITEMS",
        "keywords.results.reason: only null in the sample data; declare its type in KNOWN_NULLABLE",
    ]


def test_diff_shapes_names_added_removed_and_changed_paths():
    before = shape_of({"top_journals": [{"name": "J", "count": 1}], "total": 1, "summary": {"cagr": 1.0}})
    after = shape_of({"top_journals": [{"name": "J", "pub_count": 1}], "total": "1", "summary": {"cagr": None}})

    assert diff_shapes(before, after, "journals") == [
        "changed journals.summary.cagr: number -> null",
        "removed journals.top_journals[].count (was number)",
        "added journals.top_journals[].pub_count (number)",
        "changed journals.total: number -> string",
    ]


def test_known_items_match_backend_output(client, db):
    bursts = _detect_bursts(
        {"simulation": Counter({2019: 3, 2020: 3, 2021: 3})},
        Counter({2019: 100, 2020: 100, 2021: 3}),
    )
    assert bursts, "synthetic input no longer produces a burst; adjust it"
    assert shape_of(bursts[0]) == KNOWN_ITEMS["keywords"]["results.burst_terms"]

    project_id = client.post("/api/projects/sample").json()["id"]
    citing, cited = db.query(Publication).filter(Publication.project_id == project_id).limit(2).all()
    db.add(Citation(citing_publication_id=citing.id, cited_publication_id=cited.id))
    db.commit()
    links = analyze_citations(db, project_id)["citation_network"]["links"]
    assert links, "seeded Citation row did not reach citation_network"
    assert shape_of(links[0]) == KNOWN_ITEMS["citations"]["results.citation_network.links"]


def test_api_shapes_fixture_matches_backend(client):
    rendered = render(collect_api_shapes(client))

    if os.environ.get(UPDATE_ENV_VAR) == "1":
        SHAPES_PATH.parent.mkdir(parents=True, exist_ok=True)
        SHAPES_PATH.write_text(rendered, encoding="utf-8", newline="\n")
        return

    assert SHAPES_PATH.exists(), (
        f"{SHAPES_PATH} is missing. Generate it with: {UPDATE_ENV_VAR}=1 pytest tests/test_api_shapes_contract.py"
    )
    checked_in = json.loads(SHAPES_PATH.read_text(encoding="utf-8"))
    drift = diff_shapes(_as_object(checked_in), _as_object(json.loads(rendered)), "api-shapes")
    assert not drift, (
        f"{SHAPES_PATH.name} is stale: an analysis response shape changed.\n"
        + "\n".join(drift)
        + f"\nRefresh it with `{UPDATE_ENV_VAR}=1 pytest tests/test_api_shapes_contract.py`, then update "
        "frontend/e2e/mock-api.ts until `npx playwright test api-contract` passes."
    )


def _as_object(shapes: dict) -> dict:
    return {"type": "object", "properties": shapes}
