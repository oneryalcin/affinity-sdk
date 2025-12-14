#!/usr/bin/env python3
"""
Validate SDK models against Affinity's official V2 OpenAPI specification.

This script fetches the OpenAPI schema and compares it against the SDK's
Pydantic models, reporting any discrepancies.

TR-013: OpenAPI Schema Alignment (V2)

Usage:
    python tools/validate_openapi_models.py [--verbose] [--offline <path>]

Exit codes:
    0 - All models are compatible
    1 - Validation errors found
    2 - Schema fetch/parse error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel

# Default OpenAPI schema URL
OPENAPI_SCHEMA_URL = (
    "https://raw.githubusercontent.com/yaniv-golan/affinity-api-docs/main/docs/v2/openapi.json"
)

# Known SDK extensions beyond OpenAPI (documented exceptions)
# These fields are hand-written extensions that are permitted per TR-013
KNOWN_EXTENSIONS: dict[str, set[str]] = {
    # FieldValues container and V1->V2 normalization fields
    "Person": {"organization_ids", "opportunity_ids", "interaction_dates", "fields"},
    "Company": {
        "person_ids",
        "opportunity_ids",
        "list_entries",
        "interaction_dates",
        "fields",
        "is_global",  # V1 field, aliased from "global"
    },
    "Opportunity": {"fields", "person_ids", "organization_ids", "list_entries"},
    "ListEntry": {"fields", "entity_id", "entity_type", "entity"},
    # V1-only models that don't exist in V2 OpenAPI
    "AffinityList": {"type", "is_public", "list_size", "fields", "additional_permissions"},
    "SavedView": {"list_id", "is_default", "field_ids"},  # V1 fields
    "FieldMetadata": {
        "allows_multiple",
        "list_id",
        "track_changes",
        "is_required",
        "dropdown_options",
    },
}

# Model name mappings (SDK name -> OpenAPI schema name)
MODEL_MAPPINGS: dict[str, str] = {
    "AffinityList": "List",
    "ListSummary": "ListSummary",
    "PersonSummary": "PersonSummary",
    "CompanySummary": "CompanySummary",
}

# Known V1-only models that don't have V2 OpenAPI schemas
# These are expected to be missing from the schema and should not trigger warnings
V1_ONLY_MODELS: set[str] = {
    # V1-only entities
    "Note",
    "NoteV2",
    "Interaction",
    "Reminder",
    "WebhookSubscription",
    "EntityFile",
    "FieldValueChange",
    # Beta/internal models
    "MergeTask",
    # SDK convenience types (summaries, nested types)
    "PersonSummary",
    "CompanySummary",
    "ListSummary",
    "ListPermission",
    "DropdownOption",
    # V1-heavy models with different structures
    "ListEntryWithEntity",
    "FieldValue",
}


@dataclass
class ValidationResult:
    """Result of validating a single model."""

    model_name: str
    schema_name: str
    missing_in_sdk: list[str] = field(default_factory=list)
    extra_in_sdk: list[str] = field(default_factory=list)
    type_mismatches: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    is_v1_only: bool = False  # Model is known to be V1-only (expected not in schema)

    @property
    def is_compatible(self) -> bool:
        """Check if the model is compatible (no errors, only warnings)."""
        return not self.missing_in_sdk and not self.type_mismatches

    def __str__(self) -> str:
        lines = [f"\n=== {self.model_name} (schema: {self.schema_name}) ==="]
        if self.is_v1_only:
            lines.append("  [SKIP] V1-only model (no V2 schema expected)")
        elif self.is_compatible and not self.extra_in_sdk and not self.warnings:
            lines.append("  [OK] Compatible")
        else:
            if self.missing_in_sdk:
                lines.append("  [ERROR] Missing in SDK:")
                for field_name in self.missing_in_sdk:
                    lines.append(f"      - {field_name}")
            if self.extra_in_sdk:
                lines.append("  [INFO] Extra in SDK (extensions):")
                for field_name in self.extra_in_sdk:
                    lines.append(f"      - {field_name}")
            if self.type_mismatches:
                lines.append("  [ERROR] Type mismatches:")
                for mismatch in self.type_mismatches:
                    lines.append(f"      - {mismatch}")
            if self.warnings:
                lines.append("  [WARN] Warnings:")
                for warning in self.warnings:
                    lines.append(f"      - {warning}")
        return "\n".join(lines)


def fetch_openapi_schema(url: str) -> dict[str, Any]:
    """Fetch the OpenAPI schema from URL."""
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            result: dict[str, Any] = json.loads(response.read().decode("utf-8"))
            return result
    except Exception as e:
        raise RuntimeError(f"Failed to fetch OpenAPI schema: {e}") from e


def load_openapi_schema(path: str) -> dict[str, Any]:
    """Load the OpenAPI schema from a local file."""
    with Path(path).open() as f:
        result: dict[str, Any] = json.load(f)
        return result


def get_schema_properties(
    schema: dict[str, Any],
    component_name: str,
) -> dict[str, dict[str, Any]] | None:
    """Extract properties from an OpenAPI component schema."""
    components = schema.get("components", {}).get("schemas", {})
    if component_name not in components:
        return None

    component = components[component_name]

    # Handle allOf composition
    if "allOf" in component:
        properties: dict[str, dict[str, Any]] = {}
        for sub_schema in component["allOf"]:
            if "$ref" in sub_schema:
                ref_name = sub_schema["$ref"].split("/")[-1]
                ref_props = get_schema_properties(schema, ref_name)
                if ref_props:
                    properties.update(ref_props)
            elif "properties" in sub_schema:
                properties.update(sub_schema["properties"])
        return properties

    result: dict[str, dict[str, Any]] = component.get("properties", {})
    return result


def normalize_field_name(name: str) -> str:
    """Convert camelCase to snake_case."""
    # Handle common patterns
    s = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s).lower()


def get_sdk_models() -> dict[str, type]:
    """Import and return SDK model classes."""
    from affinity.models.entities import (
        AffinityList,
        Company,
        CompanySummary,
        DropdownOption,
        FieldMetadata,
        FieldValue,
        FieldValueChange,
        ListEntry,
        ListEntryWithEntity,
        ListPermission,
        ListSummary,
        Opportunity,
        Person,
        PersonSummary,
        SavedView,
    )
    from affinity.models.secondary import (
        EntityFile,
        Interaction,
        MergeTask,
        Note,
        NoteV2,
        Reminder,
        WebhookSubscription,
        WhoAmI,
    )

    return {
        # Core entities
        "Person": Person,
        "PersonSummary": PersonSummary,
        "Company": Company,
        "CompanySummary": CompanySummary,
        "Opportunity": Opportunity,
        "AffinityList": AffinityList,
        "ListSummary": ListSummary,
        "ListEntry": ListEntry,
        "ListEntryWithEntity": ListEntryWithEntity,
        "ListPermission": ListPermission,
        "SavedView": SavedView,
        # Fields
        "FieldMetadata": FieldMetadata,
        "FieldValue": FieldValue,
        "FieldValueChange": FieldValueChange,
        "DropdownOption": DropdownOption,
        # Secondary entities
        "Note": Note,
        "NoteV2": NoteV2,
        "Interaction": Interaction,
        "Reminder": Reminder,
        "WebhookSubscription": WebhookSubscription,
        "EntityFile": EntityFile,
        # Merge tasks
        "MergeTask": MergeTask,
        # Auth
        "WhoAmI": WhoAmI,
    }


def get_pydantic_fields(model: type) -> dict[str, dict[str, Any]]:
    """Extract field information from a Pydantic model."""
    if not issubclass(model, BaseModel):
        return {}

    fields: dict[str, dict[str, Any]] = {}
    for name, field_info in model.model_fields.items():
        # Get the alias (API field name) if defined
        alias = field_info.alias or name
        fields[name] = {
            "alias": alias,
            "type": field_info.annotation,
            "required": field_info.is_required(),
        }
    return fields


def validate_model(
    schema: dict[str, Any],
    sdk_model_name: str,
    sdk_model: type,
    schema_name: str | None = None,
) -> ValidationResult:
    """Validate a single SDK model against the OpenAPI schema."""
    if schema_name is None:
        schema_name = MODEL_MAPPINGS.get(sdk_model_name, sdk_model_name)

    result = ValidationResult(model_name=sdk_model_name, schema_name=schema_name)

    # Check if this is a known V1-only model
    if sdk_model_name in V1_ONLY_MODELS:
        result.is_v1_only = True
        return result

    # Get schema properties
    schema_props = get_schema_properties(schema, schema_name)
    if schema_props is None:
        result.warnings.append(f"Schema component '{schema_name}' not found in OpenAPI")
        return result

    # Get SDK fields
    sdk_fields = get_pydantic_fields(sdk_model)

    # Build lookup maps
    schema_field_names = set(schema_props.keys())
    sdk_aliases = {info["alias"]: name for name, info in sdk_fields.items()}
    sdk_alias_set = set(sdk_aliases.keys())

    # Also include snake_case versions of schema fields
    schema_normalized = {normalize_field_name(f): f for f in schema_field_names}

    # Check for missing fields in SDK
    for schema_field in schema_field_names:
        normalized = normalize_field_name(schema_field)
        # Field is present if alias matches or snake_case matches
        if schema_field not in sdk_alias_set and normalized not in {
            info["alias"] for info in sdk_fields.values()
        }:
            # Check if it's in the SDK by snake_case name
            found = any(
                name == normalized or info["alias"] == schema_field
                for name, info in sdk_fields.items()
            )
            if not found:
                result.missing_in_sdk.append(f"{schema_field}")

    # Check for extra fields in SDK (extensions)
    known_ext = KNOWN_EXTENSIONS.get(sdk_model_name, set())
    for sdk_name, info in sdk_fields.items():
        alias = info["alias"]
        normalized_alias = normalize_field_name(alias)
        # Check if this field exists in schema
        if (
            alias not in schema_field_names
            and normalized_alias not in schema_normalized
            and sdk_name not in known_ext
        ):
            result.extra_in_sdk.append(f"{sdk_name} (alias: {alias})")

    return result


def validate_all_models(
    schema: dict[str, Any],
    verbose: bool = False,
) -> list[ValidationResult]:
    """Validate all SDK models against the OpenAPI schema."""
    results: list[ValidationResult] = []

    sdk_models = get_sdk_models()

    for model_name, model in sdk_models.items():
        result = validate_model(schema, model_name, model)
        results.append(result)

        if verbose:
            print(result)

    return results


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate SDK models against OpenAPI schema")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print detailed output")
    parser.add_argument(
        "--offline",
        metavar="PATH",
        help="Use local OpenAPI schema file instead of fetching",
    )
    parser.add_argument(
        "--url",
        default=OPENAPI_SCHEMA_URL,
        help=f"OpenAPI schema URL (default: {OPENAPI_SCHEMA_URL})",
    )
    args = parser.parse_args()

    try:
        if args.offline:
            print(f"Loading OpenAPI schema from {args.offline}...")
            schema = load_openapi_schema(args.offline)
        else:
            print(f"Fetching OpenAPI schema from {args.url}...")
            schema = fetch_openapi_schema(args.url)
        print("Schema loaded successfully.\n")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    # Extract v2 version info if available
    info = schema.get("info", {})
    version = info.get("version", "unknown")
    print(f"OpenAPI spec version: {version}")

    # Validate models
    results = validate_all_models(schema, verbose=args.verbose)

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    # Categorize results
    v1_only = [r for r in results if r.is_v1_only]
    v2_results = [r for r in results if not r.is_v1_only]
    compatible = [r for r in v2_results if r.is_compatible and not r.warnings]
    with_extensions = [
        r for r in v2_results if r.is_compatible and r.extra_in_sdk and not r.warnings
    ]
    incompatible = [r for r in v2_results if not r.is_compatible and not r.warnings]
    not_found = [r for r in v2_results if any("not found" in w for w in r.warnings)]

    print(f"[OK] V2 compatible models: {len(compatible) + len(with_extensions)}")
    if with_extensions:
        print(f"     (includes {len(with_extensions)} with documented extensions)")
    print(f"[SKIP] V1-only models: {len(v1_only)} (no V2 schema expected)")
    if incompatible:
        print(f"[ERROR] Incompatible models: {len(incompatible)}")
    if not_found:
        print(f"[WARN] Unexpected models not in schema: {len(not_found)}")

    if incompatible:
        print("\nIncompatible models:")
        for r in incompatible:
            print(
                f"  - {r.model_name}: {len(r.missing_in_sdk)} missing, "
                f"{len(r.type_mismatches)} type mismatches"
            )

    if not_found:
        print("\nUnexpected models not in schema:")
        for r in not_found:
            print(f"  - {r.model_name}")

    # Return error if any models are incompatible
    if incompatible:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
