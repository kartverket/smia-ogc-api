import yaml


def add_styles_paths(spec: dict, config: dict) -> None:
    paths = spec["paths"]
    error_schema = {
        "type": "object",
        "required": ["code", "description"],
        "properties": {
            "code": {"type": "string"},
            "description": {"type": "string"},
        },
    }

    for collection_id, resource in config["resources"].items():
        if resource.get("type") != "collection" or not resource.get("styles"):
            continue

        collection_path = f"/collections/{collection_id}"
        if collection_path not in paths:
            raise ValueError(f"OpenAPI collection path is missing: {collection_path}")
        tags = paths[collection_path]["get"]["tags"]

        paths[f"{collection_path}/styles"] = {
            "get": {
                "summary": f"List styles for {collection_id}",
                "tags": tags,
                "operationId": f"get{collection_id.capitalize()}Styles",
                "parameters": [{"$ref": "#/components/parameters/lang"}],
                "responses": {
                    "200": {
                        "description": "Available styles",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "required": ["styles"],
                                    "properties": {
                                        "styles": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "required": [
                                                    "id",
                                                    "title",
                                                    "description",
                                                    "links",
                                                ],
                                                "properties": {
                                                    "id": {"type": "string"},
                                                    "title": {"type": "string"},
                                                    "description": {"type": "string"},
                                                    "links": {
                                                        "type": "array",
                                                        "items": {
                                                            "type": "object",
                                                            "required": [
                                                                "rel",
                                                                "href",
                                                                "type",
                                                            ],
                                                            "properties": {
                                                                "rel": {
                                                                    "type": "string"
                                                                },
                                                                "href": {
                                                                    "type": "string"
                                                                },
                                                                "type": {
                                                                    "type": "string"
                                                                },
                                                            },
                                                        },
                                                    },
                                                },
                                            },
                                        },
                                        "default": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "404": {
                        "description": "Collection not found",
                        "content": {"application/json": {"schema": error_schema}},
                    },
                },
            }
        }
        paths[f"{collection_path}/styles/{{style_id}}"] = {
            "get": {
                "summary": f"Get a style for {collection_id}",
                "tags": tags,
                "operationId": f"get{collection_id.capitalize()}Style",
                "parameters": [
                    {
                        "name": "style_id",
                        "in": "path",
                        "required": True,
                        "schema": {"type": "string"},
                    },
                    {
                        "name": "f",
                        "in": "query",
                        "required": False,
                        "schema": {
                            "type": "string",
                            "enum": ["mbs", "mapbox"],
                            "default": "mbs",
                        },
                    },
                ],
                "responses": {
                    "200": {
                        "description": "Mapbox style document",
                        "content": {
                            "application/vnd.mapbox.style+json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "version": {"type": "integer"},
                                        "sources": {"type": "object"},
                                        "layers": {
                                            "type": "array",
                                            "items": {"type": "object"},
                                        },
                                    },
                                }
                            }
                        },
                    },
                    "400": {
                        "description": "Unsupported style format",
                        "content": {"application/json": {"schema": error_schema}},
                    },
                    "404": {
                        "description": "Collection or style not found",
                        "content": {"application/json": {"schema": error_schema}},
                    },
                    "500": {
                        "description": "Style document is not valid JSON",
                        "content": {"application/json": {"schema": error_schema}},
                    },
                },
            }
        }


def add_styles_to_openapi(openapi_path: str, config_path: str) -> None:
    with open(config_path, encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    with open(openapi_path, encoding="utf-8") as openapi_file:
        spec = yaml.safe_load(openapi_file)

    add_styles_paths(spec, config)

    with open(openapi_path, "w", encoding="utf-8") as openapi_file:
        yaml.safe_dump(spec, openapi_file, allow_unicode=True, sort_keys=False)
