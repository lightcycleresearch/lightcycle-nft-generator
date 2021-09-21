from datetime import datetime, timezone
from pprint import pformat
from shutil import copyfile
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


class TokenTool:
    TEMPLATE = {
        "attributes": [
            # {"trait_type": "color", "value": "white"},
        ],
        "collection": None,
        "description": None,
        "image": None,
        "name": None,
        "properties": {
            "category": "image",
            "creators": [
                {
                    "address": None,
                    "share": 100,
                }
            ],
            "files": None,
        },
        "seller_fee_basis_points": None,
        "symbol": None,
    }

    def __init__(self, config, project_name):
        self.config = config
        self.project_name = project_name

    def random_attributes(self):
        traits = self.config[self.project_name]["traits"]

        # wildcard
        wildcard_categories = {}
        for trait in traits["trait_values"]:
            try:
                wildcard_values = traits["trait_values"][trait]["any"]
            except KeyError:
                pass
            else:
                wildcard_categories[trait] = wildcard_values
        logger.info(pformat(wildcard_categories))

        # select wildcard for any
        selected_wildcards = {}
        for k, v in wildcard_categories.items():
            logger.info(f"{k} {v}")
            selections = random.choices(
                population=list(v.keys()),
                weights=list(v.values()),
            )
            selected_wildcards[k] = selections[0]
        logger.info(pformat(selected_wildcards))

        # select sublevels
        selected_sublevels = {}
        for trait in traits["trait_values"]:
            if trait in wildcard_categories.keys():
                logger.info(f"Skip wildcard {trait=}")

            for k, v in selected_wildcards.items():
                try:
                    x = traits["trait_values"][trait][v]
                except KeyError:
                    continue
                selections = random.choices(
                    population=list(x.keys()),
                    weights=list(x.values()),
                )
                selected_sublevels[trait] = selections[0]
        logger.info(pformat(selected_sublevels))

        # combine
        combo = {**selected_wildcards, **selected_sublevels}
        logger.info(pformat(combo))
        return combo

    def set_project_values(self, metadata):
        s = self.config[self.project_name]["settings"]

        # collection
        assert not metadata["collection"]
        assert not metadata["description"]
        assert not metadata["symbol"]
        metadata["collection"] = s["collection"]
        metadata["description"] = s["description"]
        metadata["symbol"] = s["symbol"]
        metadata["seller_fee_basis_points"] = s["seller_fee_basis_points"]

        # addresses
        assert len(metadata["properties"]["creators"]) == 1
        metadata["properties"]["creators"][0]["address"] = s["address"]

    def set_token_values(self, metadata, token_num, attributes):
        """overwrite token specific placeholders"""
        s = self.config[self.project_name]["settings"]
        name_prefix = s["name_prefix"]

        image_fname = f"{token_num}.png"
        metadata["image"] = image_fname
        metadata["name"] = f"{name_prefix} #{token_num}"

        # new files list
        metadata["properties"]["files"] = []
        metadata["properties"]["files"].append(
            {"type": "image/png", "uri": image_fname}
        )
        logger.info(pformat(metadata))
        raise

        # new attributes list
        metadata["attributes"] = []
        for trait_type, trait_value in attributes.items():
            metadata["attributes"].append(
                {"trait_type": trait_type, "trait_value": trait_value}
            )

    def token_metadata_from_attributes(self, token_num, attributes):
        """
        Args:
            token_num (int): token number
            attributes (dict): key=trait_type, value=trait_value
        """
        assert token_num >= 0

        metadata = self.TEMPLATE.copy()
        self.set_project_values(metadata)
        self.set_token_values(
            metadata=metadata, token_num=token_num, attributes=attributes
        )

        return metadata

    def generate(self, start, end):
        """
        Args:
            start (int): integer
            end (int): integer
        """
        metadatas = []
        for token_num in range(start, end):
            logger.info(f"Genearting {token_num}")
            attributes = self.random_attributes()
            md = self.token_metadata_from_attributes(
                token_num=token_num, attributes=attributes
            )
            logger.info(pformat(md))
            metadatas.append(md)
        return metadatas

    def _validate_metadata(self, metadata):
        md = metadata
        token_name = md["name"]
        token_num = int(token_name.split("#")[-1])
        image_fname = md["image"]

        if token_num != int(image_fname.split(".")[0]):
            raise ValueError(f"image fname doesnt match {token_num} {image_fname=}")

        logger.info(pformat(md["properties"]["files"]))
        uri_fname = md["properties"]["files"][0]["uri"]
        logger.info(f"{token_num=} {int(uri_fname.split('.')[0])}")
        if token_num != int(uri_fname.split(".")[0]):
            raise ValueError(f"{token_num=} does not match {uri_fname=}")

    def save_metadatas(self, metadatas, overwrite=False):
        """
        Args:
            metadatas (list of metadata): metadata metaplex formt
        """
        project_fdpath = get_project_fdpath(
            config=self.config, project_name=self.project_name
        )
        metadata_fdpath = os.path.join(project_fdpath, "metadata")
        for md in metadatas:
            self._validate_metadata(metadata=md)

            token_name = md["name"]
            token_num = int(token_name.split("#")[-1])

            # generate
            metadata_fname = f"{token_num}.json"
            fpath = os.path.join(metadata_fdpath, metadata_fname)
            if os.path.exists(fpath) and not overwrite:
                logger.warning(f"Skip existing {metadata_fname}")
                continue

            with open(fpath, "w", encoding="utf-8") as f:
                json.dump(md, f, indent=4)
            logger.info(f"Saving {token_name} -> {metadata_fname}")


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


def get_project_fdpath(config, project_name):
    working_dir = config[project_name]["settings"]["working_dir"]
    return os.path.join(BASE_DIR, working_dir, project_name)


def create_scaffolding_basic(project_fdpath, traits):
    """
    Args:
        traits (dict): config[project_name]["traits"]
    """

    assert traits["trait_algorithm"] == "basic"
    for trait_type in traits["trait_types"]:
        trait_type_fdpath = os.path.join(project_fdpath, "traits", trait_type)
        try:
            os.makedirs(trait_type_fdpath)
        except FileExistsError:
            pass


def create_scaffolding_restricted(project_fdpath, traits):
    """
    Args:
        traits (dict): config[project_name]["traits"]
    """

    assert traits["trait_algorithm"] == "restricted"
    for trait_type in traits["trait_types"]:
        trait_type_fdpath = os.path.join(project_fdpath, "traits", trait_type)
        trait_restrictions = traits["trait_restrictions"]

        # restrictions are only one level
        if trait_type in trait_restrictions:
            try:
                os.makedirs(trait_type_fdpath)
            except FileExistsError:
                pass
            continue

        # if it has restrictions, then more levels
        sub_restrictions = traits["trait_values"][trait_type].keys()
        for sub_restriction in sub_restrictions:
            trait_fdpath = os.path.join(trait_type_fdpath, sub_restriction)
            try:
                os.makedirs(trait_fdpath)
            except FileExistsError:
                pass


def ensure_fdpath(fdpath):
    try:
        os.makedirs(fdpath)
    except FileExistsError:
        pass


def create_scaffolding_combo(project_fdpath, traits):
    """
    Args:
        traits (dict): config[project_name]["traits"]
    """

    assert traits["trait_algorithm"] == "combo"

    fdpaths = []
    for trait_type in traits["trait_types"]:

        # hidden
        if trait_type in traits["trait_hidden"]:
            logger.info(f"skip hidden {trait_type=}")
            continue

        # sublevels
        trait_type_fdpath = os.path.join(project_fdpath, "traits", trait_type)
        sublevels = traits["trait_values"][trait_type].keys()
        for sublevel in sublevels:
            fdpaths.append(os.path.join(trait_type_fdpath, sublevel))

    # create fdpaths
    for fdpath in fdpaths:
        ensure_fdpath(fdpath)


def initialize_project_folder(config, project_name):
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
    logger.info(f"Initializing {project_fdpath} folders")
    for subfolder in ["metadata", "images", "assets"]:
        ensure_fdpath(os.path.join(project_fdpath, subfolder))

    trait_algorithm = config[project_name]["traits"]["trait_algorithm"]
    traits = config[project_name]["traits"]
    if trait_algorithm == "basic":
        create_scaffolding_basic(project_fdpath=project_fdpath, traits=traits)
    elif trait_algorithm == "restricted":
        create_scaffolding_restricted(project_fdpath=project_fdpath, traits=traits)
    elif trait_algorithm == "combo":
        create_scaffolding_combo(project_fdpath=project_fdpath, traits=traits)
    else:
        raise ValueError(f"invalid {trait_algorithm=}")
    logger.info(f"DONE!  Please place your images in {project_fdpath}/traits")


def generate_metadata_project(config, project_name, overwrite=False):
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
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
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
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


def combine_assets_project(config, project_name, overwrite=False):
    # paths
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
    metadata_fdpath = os.path.join(project_fdpath, "metadata")
    images_fdpath = os.path.join(project_fdpath, "images")
    assets_fdpath = os.path.join(project_fdpath, "assets")

    try:
        os.makedirs(assets_fdpath)
    except FileExistsError:
        pass

    for token_num in range(0, num_tokens):

        # source
        image_fname = f"{token_num}.png"
        metadata_fname = f"{token_num}.json"

        image_source = os.path.join(images_fdpath, image_fname)
        metadata_source = os.path.join(metadata_fdpath, metadata_fname)

        image_dest = os.path.join(assets_fdpath, image_fname)
        metadata_dest = os.path.join(assets_fdpath, metadata_fname)

        if not args.overwrite and (
            os.path.exists(image_dest) or os.path.exists(metadata_dest)
        ):
            logger.warning(
                f"{image_fname} or {metadata_fname} already exist. You must pass --overwrite to overwrite"
            )
            continue

        logger.info(f"Combining assets for {token_num}")
        # copy to assets
        copyfile(image_source, image_dest)
        copyfile(metadata_source, metadata_dest)


def react_env_for_project(
    config,
    project_name,
    react_env_candy_machine_id,
    env="devnet",
    react_env_start_date=None,
    override_treasury_address=None,
):
    react_env_dict = {}

    if not react_env_candy_machine_id:
        raise ValueError("--react-env-candy-machine-id required")
    react_env_dict["REACT_APP_CANDY_MACHINE_ID"] = react_env_candy_machine_id

    # devnet/mainnet
    if env == "devnet":
        react_env_dict[
            "REACT_APP_SOLANA_RPC_HOST"
        ] = "https://explorer-api.devnet.solana.com"
    elif env == "mainnet-beta":
        react_env_dict[
            "REACT_APP_SOLANA_RPC_HOST"
        ] = "https://api.mainnet-beta.solana.com"
    else:
        raise NotImplementedError
    react_env_dict["REACT_APP_SOLANA_NETWORK"] = env

    # program config
    fname = f"{env}-temp"
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
    fpath = os.path.join(project_fdpath, ".cache", fname)
    try:
        with open(fpath, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except FileNotFoundError:
        logger.error(f"🔴You do not have a cache: {fpath}")
        sys.exit()
    else:
        program_config = program_config_from_cache(payload)
        react_env_dict["REACT_APP_CANDY_MACHINE_CONFIG"] = program_config

    # start date
    if react_env_start_date:
        react_env_dict["REACT_APP_CANDY_START_DATE"] = start_date_to_timestamp(
            react_env_start_date
        )
        react_env_dict["# Start Date "] = react_env_start_date
    else:
        now = datetime.now(timezone.utc)
        logger.info(f"using timestamp: {now.isoformat()=}")
        react_env_dict["REACT_APP_CANDY_START_DATE"] = int(now.timestamp())
        react_env_dict["# Start Date"] = now.strftime("%d %b %Y %H:%M:%S GMT")

    # treasury
    creator_address = config[project_name]["settings"]["address"]
    if override_treasury_address:
        pubkey = su.solana_keygen_pubkey(override_treasury_address)
        logger.info(f"overriding creator {creator_address} with {pubkey}")
        react_env_dict["REACT_APP_TREASURY_ADDRESS"] = pubkey
    else:
        react_env_dict["REACT_APP_TREASURY_ADDRESS"] = creator_address

    # stdout
    for k, v in react_env_dict.items():
        print(f"{k}={v}")


def generate_metadata_project_new(config, project_name, overwrite=False):
    tt = TokenTool(config=config, project_name=project_name)
    metadatas = tt.generate(0, 2)
    tt.save_metadatas(metadatas=metadatas, overwrite=overwrite)
