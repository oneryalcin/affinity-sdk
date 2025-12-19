from __future__ import annotations

from affinity.models.entities import FieldMetadata
from affinity.models.types import FieldValueType, to_v1_value_type_code


def test_field_metadata_parses_v2_string_value_types() -> None:
    meta = FieldMetadata.model_validate(
        {
            "id": "field-123",
            "name": "Example",
            "valueType": "ranked-dropdown",
            "allowsMultiple": False,
        }
    )
    assert isinstance(meta.value_type, FieldValueType)
    assert meta.value_type == FieldValueType.RANKED_DROPDOWN
    assert meta.value_type_raw == "ranked-dropdown"


def test_field_metadata_preserves_multi_suffix_and_coerces_allows_multiple() -> None:
    meta = FieldMetadata.model_validate(
        {
            "id": "field-123",
            "name": "Example",
            "valueType": "person-multi",
            "allowsMultiple": False,
        }
    )
    assert meta.value_type == FieldValueType.PERSON_MULTI
    assert meta.allows_multiple is True


def test_field_metadata_round_trips_unknown_value_type_as_open_enum() -> None:
    meta = FieldMetadata.model_validate(
        {
            "id": "field-123",
            "name": "Example",
            "valueType": "some-new-type",
            "allowsMultiple": False,
        }
    )
    assert isinstance(meta.value_type, FieldValueType)
    assert str(meta.value_type) == "some-new-type"
    assert meta.value_type_raw == "some-new-type"

    dumped = meta.model_dump(by_alias=True, mode="json")
    assert dumped["valueType"] == "some-new-type"

    reparsed = FieldMetadata.model_validate(dumped)
    assert isinstance(reparsed.value_type, FieldValueType)
    assert str(reparsed.value_type) == "some-new-type"
    assert reparsed.value_type_raw == "some-new-type"


def test_field_metadata_normalizes_v1_numeric_value_type_codes() -> None:
    meta = FieldMetadata.model_validate(
        {
            "id": "field-123",
            "name": "Example",
            "value_type": 7,  # v1 payloads use snake_case
            "allows_multiple": False,
        }
    )
    assert meta.value_type == FieldValueType.DROPDOWN
    assert meta.value_type_raw == 7

    dumped = meta.model_dump(by_alias=True, mode="json")
    assert dumped["valueType"] == "dropdown"


def test_to_v1_value_type_code_maps_known_types() -> None:
    assert to_v1_value_type_code(value_type=FieldValueType.NUMBER_MULTI) == 3
    assert to_v1_value_type_code(value_type=FieldValueType.LOCATION_MULTI) == 5
    assert to_v1_value_type_code(value_type=FieldValueType.RANKED_DROPDOWN) == 7
    assert to_v1_value_type_code(value_type=FieldValueType.FILTERABLE_TEXT_MULTI) == 10
    assert to_v1_value_type_code(value_type=FieldValueType.INTERACTION) is None
