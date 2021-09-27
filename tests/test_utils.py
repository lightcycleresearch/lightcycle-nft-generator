import os
import sys

# third-party
import pytest
import yaml

# src
TEST_DIR = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(TEST_DIR, ".."))
import src.utils as su


def test_validation_fail():
    config = yaml.safe_load(
        """example:
  settings:
    address: REPLACEME
"""
    )
    with pytest.raises(su.ValidationException):
        su.validate_config(config=config, project_name="example")

    with pytest.raises(su.ValidationException):
        su.validate_config(config=config, project_name="missing")


def test_validation_pass():
    config = yaml.safe_load(
        """example:
  settings:
    address: OK
"""
    )
    assert su.validate_config(config=config, project_name="example")


def test_generate_random_attributes_without_trait_restrictions():
    traits = {
        "trait_types": ["top", "bottom"],
        "trait_values": {
            "top": {"black": 1, "red": 2},
            "bottom": {"blue": 1, "green": 2},
        },
    }
    metadata_attributes = su.generate_random_attributes(traits=traits)
    assert metadata_attributes
    for trait in metadata_attributes:
        ttype = trait["trait_type"]
        assert ttype in traits["trait_values"].keys()


def test_generate_random_attributes_with_trait_restrictions():
    traits = {
        "trait_types": ["class", "body", "head", "hat"],
        "trait_restrictions": ["class"],
        "trait_values": {
            "class": {"archer": 2, "warrior": 1},
            "body": {"archer": {"orange": 1, "white": 1}, "warrior": {"white": 1}},
            "head": {"archer": {"normal": 1, "angry": 1}, "warrior": {"angry": 1}},
            "hat": {
                "archer": {"long": 1, "short": 1},
                "warrior": {"long": 1, "short": 1},
            },
        },
    }
    metadata_attributes = su.generate_random_attributes(traits=traits)
    assert metadata_attributes
    for trait in metadata_attributes:
        ttype = trait["trait_type"]
        assert ttype in traits["trait_values"].keys()


def test_simplify():
    nft_attributes = [
        {"trait_type": "class", "trait_value": "archer"},
        {"trait_type": "body", "trait_value": "orange"},
        {"trait_type": "head", "trait_value": "angry"},
        {"trait_type": "hat", "trait_value": "short"},
    ]
    flattened = su.flatten_nft_attributes(nft_attributes=nft_attributes)
    assert flattened["class"] == "archer"
    assert flattened["body"] == "orange"
    assert flattened["head"] == "angry"
    assert flattened["hat"] == "short"


def test_parse_cache():
    cache_payload = {
        "program": {
            "uuid": "LightR",
            "config": "LightRxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
        },
        "items": {
            "0": {
                "link": "https://arweave.net/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "name": "hero #0",
                "onChain": True,
            },
            "1": {
                "link": "https://arweave.net/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "name": "hero #1",
                "onChain": True,
            },
            "2": {
                "link": "https://arweave.net/xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "name": "hero #2",
                "onChain": True,
            },
        },
    }
    program_config = su.program_config_from_cache(cache_payload)
    assert program_config == "LightRxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"


def test_parse_start_date_to_timestamp():
    assert su.start_date_to_timestamp("01 Jan 2021 00:00:00 GMT") == 1609459200
    assert su.start_date_to_timestamp("15 Mar 2021 12:34:56 GMT") == 1615811696
    assert su.start_date_to_timestamp("31 Dec 2021 00:00:00 GMT") == 1640908800


def test_find_sublevel():
    sublevels = su.find_sublevels(
        {"archer": {"bow": 1, "arrow": 1}, "warrior": {"sword": 1}}
    )
    assert sublevels["bow"] == "archer"
    assert sublevels["arrow"] == "archer"
    assert sublevels["sword"] == "warrior"


def test_apply_translation():
    orig_metadata = {
        "attributes": [
            {"trait_type": "trait0", "trait_value": "unchanged0"},
            {"trait_type": "trait1", "trait_value": "unchanged1"},
            {"trait_type": "trait2", "trait_value": "unchanged2"},
        ]
    }

    translation = {
        "unchanged0": "english0",
        "unchanged1": "  english1  ",
        "unchanged2": "english2",
    }
    metadata = su.apply_translation(metadata=orig_metadata, translation=translation)
    assert metadata["attributes"][0]["trait_value"] == "english0"
    assert metadata["attributes"][1]["trait_value"] == "english1"
    assert metadata["attributes"][2]["trait_value"] == "english2"


def test_apply_translation_empty():
    orig_metadata = {
        "attributes": [
            {"trait_type": "trait0", "trait_value": "unchanged0"},
            {"trait_type": "trait1", "trait_value": "unchanged1"},
            {"trait_type": "trait2", "trait_value": "unchanged2"},
        ]
    }
    translation = None

    metadata = su.apply_translation(metadata=orig_metadata, translation=translation)
    assert metadata["attributes"][0]["trait_value"] == "unchanged0"
    assert metadata["attributes"][1]["trait_value"] == "unchanged1"
    assert metadata["attributes"][2]["trait_value"] == "unchanged2"


def test_apply_translation_do_not_change_empty():
    orig_metadata = {
        "attributes": [
            {"trait_type": "trait0", "trait_value": "unchanged0"},
            {"trait_type": "trait1", "trait_value": "unchanged1"},
            {"trait_type": "trait2", "trait_value": "unchanged2"},
        ]
    }

    translation = {
        "unchanged0": "english0",
        # REMOVED - unchanged1
        "unchanged2": "english2",
    }
    metadata = su.apply_translation(
        metadata=orig_metadata, translation=translation, handle_missing=None
    )
    assert metadata["attributes"][0]["trait_value"] == "english0"
    assert metadata["attributes"][1]["trait_value"] == "unchanged1"
    assert metadata["attributes"][2]["trait_value"] == "english2"


def test_apply_translation_fail_with_aon():
    orig_metadata = {
        "attributes": [
            {"trait_type": "trait0", "trait_value": "unchanged0"},
            {"trait_type": "trait1", "trait_value": "unchanged1"},
            {"trait_type": "trait2", "trait_value": "unchanged2"},
        ]
    }

    translation = {
        "unchanged0": "english0",
        # REMOVED - unchanged1
        "unchanged2": "english2",
    }
    with pytest.raises(ValueError):
        metadata = su.apply_translation(
            metadata=orig_metadata,
            translation=translation,
            handle_missing="fail",
        )


def test_apply_media_host():
    orig_metadata = {
        "image": "0.png",
        "properties": {"files": [{"type": "image/png", "uri": "0.png"}]},
    }

    media_host = {
        "0.png": "https://www.example.com/abcd?ext=png",
        "1.png": "https://www.example.com/efgh?ext=png",
        "2.png": "https://www.example.com/ijkl?ext=png",
    }
    metadata = su.apply_media_host(metadata=orig_metadata, media_host=media_host)
    assert metadata["image"] == "https://www.example.com/abcd?ext=png"
    assert (
        metadata["properties"]["files"][0]["uri"]
        == "https://www.example.com/abcd?ext=png"
    )
