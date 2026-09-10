"""OpenAPI regression coverage without a server or application lifespan."""

import json

from fastapi.openapi.models import OpenAPI
from fastapi.routing import APIRoute


def test_real_app_openapi_preserves_routes_and_manual_check_body():
    from app.main import app

    cached_schema = app.openapi_schema
    try:
        app.openapi_schema = None
        document = json.loads(json.dumps(app.openapi()))
    finally:
        app.openapi_schema = cached_schema

    OpenAPI.model_validate(document)
    assert document["info"]["title"] == "API Monitor"
    paths = document["paths"]
    assert {"/health", "/api/v1/endpoints", "/api/v1/endpoints/{endpoint_id}/check"} <= paths.keys()
    for route in app.routes:
        if isinstance(route, APIRoute) and route.include_in_schema:
            assert route.path_format in paths
            assert {method.lower() for method in route.methods} <= paths[route.path_format].keys()

    # This optional model-valued body used to crash FastAPI's schema remapping.
    operation = paths["/api/v1/endpoints/{endpoint_id}/check"]["post"]
    body = operation["requestBody"]
    assert body.get("required", False) is False
    assert body["content"]["application/json"]["schema"]["default"] == {"use_retry": True}
    model = document["components"]["schemas"]["CheckManualRequest"]
    assert model["properties"]["use_retry"]["type"] == "boolean"
    assert model["properties"]["use_retry"]["default"] is True

    # Every local schema reference must resolve, not merely serialize to JSON.
    def check_references(value):
        if isinstance(value, dict):
            if "$ref" in value:
                assert value["$ref"].startswith("#/")
                target = document
                for token in value["$ref"][2:].split("/"):
                    target = target[token.replace("~1", "/").replace("~0", "~")]
            for child in value.values():
                check_references(child)
        elif isinstance(value, list):
            for child in value:
                check_references(child)

    check_references(document)
