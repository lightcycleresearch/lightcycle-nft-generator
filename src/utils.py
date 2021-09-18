from datetime import datetime, timezone
from pprint import pformat
import random
import subprocess

# logging
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ValidationException(Exception):
    pass


def validate_config(config, project_name):
    try:
        settings = config[project_name]
    except KeyError:
        raise ValidationException(
            f"Please ensure projects exist in config. Maybe: \n\t cp config.ini.example config.ini"
        )

    project_creator_address = config[project_name]["settings"]["address"]
    logger.info(
        f"creator address for project '{project_name}' is '{project_creator_address}'"
    )
    if project_creator_address == "REPLACEME":
        raise ValidationException(f"Please replace REPLACEME in config")

    return True


def generate_random_attributes(traits):
    """
    Args:
        traits (dict): TBD

    Returns:
        dict: matches metaplex standard
    """
    tv = traits["trait_values"]
    try:
        trait_restrictions = traits["trait_restrictions"]
    except KeyError:
        trait_restrictions = []

    attributes = {}

    restricted_types = [tt for tt in traits["trait_types"] if tt in trait_restrictions]
    unrestricted_types = [
        tt for tt in traits["trait_types"] if tt not in trait_restrictions
    ]
    logger.debug(restricted_types)
    logger.debug(unrestricted_types)

    # select the restrictions first
    for trait_type in restricted_types:
        total = sum(tv[trait_type].values())
        selections = random.choices(
            population=list(tv[trait_type].keys()),
            weights=list(tv[trait_type].values()),
        )
        selection = selections[0]
        attributes[trait_type] = selection

    # select non restrictions
    if restricted_types:
        for trait_type in unrestricted_types:
            for restriction in restricted_types:
                restriction_value = attributes[restriction]
                total = sum(tv[trait_type][restriction_value].values())
                selections = random.choices(
                    population=list(tv[trait_type][restriction_value].keys()),
                    weights=list(tv[trait_type][restriction_value].values()),
                )
                selection = selections[0]
                attributes[trait_type] = selection
    else:
        for trait_type in unrestricted_types:
            total = sum(tv[trait_type].values())
            selections = random.choices(
                population=list(tv[trait_type].keys()),
                weights=list(tv[trait_type].values()),
            )
            selection = selections[0]
            attributes[trait_type] = selection

    # build metaplex standard
    nft_attributes = []
    for ttype, tvalue in attributes.items():
        nft_attributes.append({"trait_type": ttype, "trait_value": tvalue})
    return nft_attributes


def flatten_nft_attributes(nft_attributes):
    """
    Args:
        nft_attributes (list of dict): keys trait_type, trait_value
    """
    flattened = {}
    for na in nft_attributes:
        flattened[na["trait_type"]] = na["trait_value"]
    return flattened


def program_config_from_cache(cache_payload):
    return cache_payload["program"]["config"]


def start_date_to_timestamp(start_date):
    """
    Args:
        start_date (str): format is 01 Jan 2021 00:00:00 GMT

    Returns:
        int: timestamp
    """
    dt = datetime.strptime(start_date, "%d %b %Y %H:%M:%S GMT")
    return int(dt.timestamp())


def solana_keygen_pubkey(keypair=None):
    cmd = [
        "solana-keygen",
        "pubkey",
    ]
    if keypair:
        cmd.append(keypair)
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    output = proc.stdout.read()
    return output.decode("utf-8")
