from datetime import datetime, timezone
from pprint import pformat
import json
import os
import random
import re
import subprocess

# third-party
from PIL import Image

# logging
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")


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


def get_project_fdpath(project_name):
    return os.path.join(BASE_DIR, "projects", project_name)


def initialize_project_folder(config, project_name):
    project_fdpath = get_project_fdpath(project_name)
    logger.info(f"Initializing {project_fdpath} folders")
    for subfolder in ["metadata", "images", "assets"]:
        try:
            os.makedirs(os.path.join(project_fdpath, subfolder))
        except FileExistsError:
            pass

    trait_types = config[project_name]["traits"]["trait_types"]
    for trait_type in trait_types:
        trait_type_fdpath = os.path.join(project_fdpath, "traits", trait_type)
        try:
            trait_restrictions = config[project_name]["traits"]["trait_restrictions"]
        except KeyError:
            trait_restrictions = []
        # restrictions are only one level
        if not trait_restrictions or trait_type in trait_restrictions:
            try:
                os.makedirs(trait_type_fdpath)
            except FileExistsError:
                pass
        else:
            # if it has restrictions, then more levels
            trait_type_restrictions = config[project_name]["traits"]["trait_values"][
                trait_type
            ].keys()
            for trait_type_restriction in trait_type_restrictions:
                trait_fdpath = os.path.join(trait_type_fdpath, trait_type_restriction)
                try:
                    os.makedirs(trait_fdpath)
                except FileExistsError:
                    pass
    logger.info(f"DONE!  Please place your images in {project_fdpath}/traits")


def generate_metadata_project(config, project_name, overwrite=False):
    project_fdpath = get_project_fdpath(project_name)
    settings = config[project_name]["settings"]
    num_tokens = int(settings["num_tokens"])
    creator_address = settings["address"]
    name_prefix = settings["name_prefix"]
    description = settings["description"]
    symbol = settings["symbol"]
    collection = settings["collection"]
    seller_fee_basis_points = int(settings["seller_fee_basis_points"])

    logger.info(f"Generating metadata for {num_tokens}")
    TEMPLATE = {
        "attributes": [
            # {"trait_type": "color", "value": "white"},
            # {"trait_type": "pattern", "value": "random"},
        ],
        "collection": collection,
        "description": description,
        "image": None,
        "name": None,
        "properties": {
            "category": "image",
            "creators": [
                {
                    "address": creator_address,
                    "share": 100,
                }
            ],
            "files": [
                {
                    "type": "image/png",
                    "uri": None,
                }
            ],
        },
        "seller_fee_basis_points": seller_fee_basis_points,
        "symbol": symbol,
    }
    for token_num in range(0, num_tokens):
        metadata = TEMPLATE.copy()
        image_fname = f"{token_num}.png"
        metadata["image"] = image_fname
        metadata["name"] = f"{name_prefix} #{token_num}"
        metadata["properties"]["files"][0]["uri"] = image_fname
        metadata["attributes"] = generate_random_attributes(
            traits=config[project_name]["traits"]
        )

        metadata_fname = f"{token_num}.json"
        metadata_fpath = os.path.join(project_fdpath, "metadata", metadata_fname)
        if os.path.exists(metadata_fpath) and not overwrite:
            logger.warning(
                f"{metadata_fname} already exists. You must pass --overwrite to overwrite"
            )
            continue

        logger.info(f"Generating metadata for token {token_num} -> {metadata}")
        logger.info(f"Creating {metadata_fpath}")
        with open(metadata_fpath, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)


def generate_images_project(config, project_name, overwrite=False):

    # paths
    project_fdpath = get_project_fdpath(project_name)
    traits_fdpath = os.path.join(project_fdpath, "traits")
    metadata_fdpath = os.path.join(project_fdpath, "metadata")
    images_fdpath = os.path.join(project_fdpath, "images")

    # sort metadata fnames as numeric and not str, so 0,1,2,3 instead of 0,10,11,12
    fnames = os.listdir(metadata_fdpath)
    fnames = [x for x in fnames if ".json" in x]
    fnames.sort(key=lambda f: int(re.sub("\D", "", f)))

    # validation
    num_tokens = config[project_name]["settings"]["num_tokens"]
    if len(fnames) != num_tokens:
        logger.error(f"🔴invalid number of files in metadata, need {num_tokens}")
        sys.exit(1)

    for i, fname in enumerate(fnames):
        assert i == int(fname.split(".")[0])

        img_fname = f"{i}.png"
        dest_img_fpath = os.path.join(images_fdpath, img_fname)
        if os.path.exists(dest_img_fpath) and not overwrite:
            logger.warning(
                f"{img_fname} already exists. You must pass --overwrite to overwrite"
            )
            continue

        logger.info(f"{i:05} \t Generating image from {fname}")
        fpath = os.path.join(metadata_fdpath, fname)
        with open(fpath, "r", encoding="utf-8") as f:
            payload = json.load(f)
        flattened = flatten_nft_attributes(payload["attributes"])
        logger.debug(flattened)

        # use order to create
        try:
            restrictions = config[project_name]["traits"]["trait_restrictions"]
        except KeyError:
            restrictions = []

        img_fpaths = []
        for ttype in config[project_name]["traits"]["trait_types"]:
            source_img_fname = flattened[ttype] + ".png"
            if restrictions and ttype in restrictions:
                source_img_fpath = os.path.join(traits_fdpath, ttype, source_img_fname)
            elif restrictions and ttype not in restrictions:
                restriction_fdname = flattened[restrictions[0]]
                source_img_fpath = os.path.join(
                    traits_fdpath, ttype, restriction_fdname, source_img_fname
                )
            else:
                source_img_fpath = os.path.join(traits_fdpath, ttype, source_img_fname)
            logger.info(f"{ttype=} {source_img_fname} {source_img_fpath}")

            img_fpaths.append(source_img_fpath)
        logger.debug(img_fpaths)
        img = None
        for img_fpath in img_fpaths:
            if img is None:
                img = Image.open(img_fpath)
                continue
            layer = Image.open(img_fpath)
            img.paste(layer, (0, 0), layer)
        img.save(dest_img_fpath, "PNG")
