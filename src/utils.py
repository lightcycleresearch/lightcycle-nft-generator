from datetime import datetime, timezone
from pprint import pformat
from shutil import copyfile
import copy
import csv
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
        assert not metadata["seller_fee_basis_points"]
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
        try:
            image_format = s["image_format"]
        except KeyError:
            image_format = "png"

        name_prefix = s["name_prefix"]
        image_fname = f"{token_num}.{image_format}"
        metadata["image"] = image_fname
        metadata["name"] = f"{name_prefix} #{token_num}"

        # new files list
        metadata["properties"]["files"] = [
            {"type": f"image/{image_format}", "uri": image_fname}
        ]
        logger.info(metadata)

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

        metadata = copy.deepcopy(self.TEMPLATE)
        self.set_project_values(metadata)
        self.set_token_values(
            metadata=metadata, token_num=token_num, attributes=attributes
        )

        return metadata

    def generate_metadatas_combo(self, start, end):
        """
        Args:
            start (int): integer
            end (int): integer
        """
        metadatas = []
        for token_num in range(start, end):
            logger.info(f"Generating {token_num}")
            attributes = self.random_attributes()
            md = self.token_metadata_from_attributes(
                token_num=token_num, attributes=attributes
            )
            logger.info(pformat(md))
            metadatas.append(md)
        return metadatas

    def generate_metadatas_csv(self, start, end):
        """Looks for a file named metadata.csv in csv folder

        Args:
            start (int): integer
            end (int): integer
        """
        project_fdpath = get_project_fdpath(
            config=self.config, project_name=self.project_name
        )
        csv_fpath = os.path.join(project_fdpath, "csv", "metadata.csv")
        metadatas = []

        with open(csv_fpath, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for i, row in enumerate(reader):
                if i == 0:
                    header = row
                    continue

                attributes = {}
                for ttype, tval in zip(header, row):
                    attributes[ttype] = tval
                logger.info(f"{attributes=}")

                token_num = i - 1
                metadatas.append(
                    self.token_metadata_from_attributes(
                        token_num=token_num, attributes=attributes
                    )
                )

        return metadatas

    def _validate_metadata(self, metadata):
        md = metadata
        token_name = md["name"]
        token_num = int(token_name.split("#")[-1])
        logger.info(f"{token_name} {token_num=}")

        image_fname = md["image"]
        if token_num != int(image_fname.split(".")[0]):
            raise ValueError(f"image fname doesnt match {token_num} {image_fname=}")

        logger.info(pformat(md["properties"]["files"]))
        uri_fname = md["properties"]["files"][0]["uri"]
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
            logger.info(f"checking {md=}")
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

    def create_image_plan(self, metadata):
        """
        Args:
            attributes (dict): key=value
            token_num (int): token number
            overwrite (bool)
        """
        attributes = {}
        for attr_pair in metadata["attributes"]:
            attributes[attr_pair["trait_type"]] = attr_pair["trait_value"]
        logger.info(f"attributes: {pformat(attributes)}")

        logger.info(attributes)
        traits = self.config[self.project_name]["traits"]
        image_plan = []
        for trait_type in traits["trait_types"]:
            if trait_type in traits["trait_hidden"]:
                logger.info(f"skip hidden {trait_type=}")
                continue

            # get image fpath
            try:
                trait_value = attributes[trait_type]
            except KeyError:
                # not all traits are in all images
                logger.info(f"skip unavailable {trait_type=}")
                continue
            logger.info(f"Looking for image fpath for {trait_type} {trait_value=}")
            image_fpath = self.create_image_fpath(
                trait_type=trait_type, trait_value=trait_value
            )
            logger.info(f"{image_fpath=}")
            image_plan.append(image_fpath)
        return image_plan

    def create_image_plans(self, metadatas):
        image_plans = {}
        for metadata in metadatas:
            token_num = int(metadata["name"].split("#")[-1])
            image_plan = self.create_image_plan(metadata=metadata)
            image_plans[token_num] = image_plan
        return image_plans

    def create_image_fpath(self, trait_type, trait_value, extension="png"):
        project_fdpath = get_project_fdpath(
            config=self.config, project_name=self.project_name
        )
        traits_fdpath = os.path.join(project_fdpath, "traits")

        traits = self.config[self.project_name]["traits"]
        if trait_type in traits["trait_hidden"]:
            return None

        # find sublevel
        try:
            sublevels = find_sublevels(traits["trait_values"][trait_type])
        except KeyError:
            sublevel = "any"
        else:
            sublevel = sublevels[trait_value]

        # create fname
        fname = f"{trait_type}-{sublevel}-{trait_value}.{extension}"
        return os.path.join(project_fdpath, "traits", trait_type, sublevel, fname)

    def save_image_plans(self, image_plans, overwrite=False):
        project_fdpath = get_project_fdpath(
            config=self.config, project_name=self.project_name
        )
        image_fdpath = os.path.join(project_fdpath, "images")
        for token_num, image_plan in image_plans.items():
            image_fpath = os.path.join(image_fdpath, f"{token_num}.png")
            if os.path.exists(image_fpath) and not overwrite:
                logger.info(f"Skipping existing {token_num}.png")
                continue

            logger.info(f"Processing {token_num} -> ...")

            img = None
            for input_fpath in image_plan:
                if img is None:
                    img = Image.open(input_fpath)
                    continue
                layer = Image.open(input_fpath)
                img.paste(layer, (0, 0), layer)
            img.save(image_fpath, "PNG")


def find_sublevels(trait_type_levels):
    sublevels = {}
    for sublevel, blob in trait_type_levels.items():
        for k in blob.keys():
            sublevels[k] = sublevel
    return sublevels


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
            try:
                total = sum(tv[trait_type].values())
            except TypeError:
                raise ValueError(f"bad rarity in {trait_type=}")
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


def create_scaffolding_csv(project_fdpath, traits):
    """
    Args:
        traits (dict): config[project_name]["traits"]
    """

    assert traits["trait_algorithm"] == "csv"
    ensure_fdpath(os.path.join(project_fdpath, "csv"))


def initialize_project_folder(config, project_name):
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
    logger.info(f"Initializing {project_fdpath} folders")
    for subfolder in ["metadata", "images", "assets", "translations", "media_hosts"]:
        ensure_fdpath(os.path.join(project_fdpath, subfolder))

    trait_algorithm = config[project_name]["traits"]["trait_algorithm"]
    traits = config[project_name]["traits"]
    if trait_algorithm == "basic":
        create_scaffolding_basic(project_fdpath=project_fdpath, traits=traits)
    elif trait_algorithm == "restricted":
        create_scaffolding_restricted(project_fdpath=project_fdpath, traits=traits)
    elif trait_algorithm == "combo":
        create_scaffolding_combo(project_fdpath=project_fdpath, traits=traits)
    elif trait_algorithm == "csv":
        create_scaffolding_csv(project_fdpath=project_fdpath, traits=traits)
    else:
        raise ValueError(f"invalid {trait_algorithm=}")
    logger.info(f"DONE!  Please place your images in {project_fdpath}/traits")


def generate_metadata_project_basic(config, project_name, overwrite=False):
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


def generate_images_project_basic(config, project_name, overwrite=False):

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


def load_csv_map(config, project_name, fdname="translations"):
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)

    # translation
    if fdname == "translations":
        try:
            translation_name = config[project_name]["traits"]["trait_translation"]
        except KeyError:
            return None
    elif fdname == "media_hosts":
        try:
            translation_name = config[project_name]["traits"]["trait_media_host"]
        except KeyError:
            return None
    else:
        raise ValueError(f"invalid {fdname=}")

    # load csv
    translations_fdpath = os.path.join(project_fdpath, fdname)
    translation_fpath = os.path.join(translations_fdpath, f"{translation_name}.csv")
    try:
        with open(translation_fpath, "r", encoding="utf-8") as f:
            t_data = f.read()
    except FileNotFoundError:
        return None

    # assemble translation
    translation = {}
    lines = t_data.split("\n")
    lines = [L for L in lines if L]
    for line in lines:
        key, value = line.split(",")
        if key in translation.keys():
            raise ValueError(
                f"duplicate {key=} found for translation {translation_name}"
            )
        translation[key] = value.strip()

    return translation


def combine_assets_project(config, project_name, overwrite=False):
    # paths
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
    s = config[project_name]["settings"]
    num_tokens = s["num_tokens"]
    try:
        image_format = s["image_format"]
    except KeyError:
        image_format = "png"

    metadata_fdpath = os.path.join(project_fdpath, "metadata")
    images_fdpath = os.path.join(project_fdpath, "images")
    assets_fdpath = os.path.join(project_fdpath, "assets")

    try:
        os.makedirs(assets_fdpath)
    except FileExistsError:
        pass

    # translation
    translation = load_csv_map(
        config=config, project_name=project_name, fdname="translations"
    )
    media_host = load_csv_map(
        config=config, project_name=project_name, fdname="media_hosts"
    )

    # tokens
    for token_num in range(0, num_tokens):

        # source
        image_fname = f"{token_num}.{image_format}"
        metadata_fname = f"{token_num}.json"

        fpath_image_source = os.path.join(images_fdpath, image_fname)
        fpath_metadata_source = os.path.join(metadata_fdpath, metadata_fname)

        fpath_image_dest = os.path.join(assets_fdpath, image_fname)
        fpath_metadata_dest = os.path.join(assets_fdpath, metadata_fname)

        if not overwrite and (
            os.path.exists(fpath_image_dest) or os.path.exists(fpath_metadata_dest)
        ):
            logger.warning(
                f"{image_fname} or {metadata_fname} already exist. You must pass --overwrite to overwrite"
            )
            continue

        logger.info(f"Combining assets for {token_num}")
        copyfile(fpath_image_source, fpath_image_dest)

        if translation is None and media_host is None:
            copyfile(fpath_metadata_source, fpath_metadata_dest)
            continue

        # translate metadata and write to final
        with open(fpath_metadata_source, "r", encoding="utf-8") as f:
            orig_metadata = json.load(f)

        if translation:
            metadata = apply_translation(
                metadata=orig_metadata, translation=translation, handle_missing="fail"
            )

        if media_host:
            raise NotImplementedError

        with open(fpath_metadata_dest, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=4)


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


def generate_metadata_project(config, project_name, overwrite=False):
    tt = TokenTool(config=config, project_name=project_name)
    num_tokens = config[project_name]["settings"]["num_tokens"]
    trait_algorithm = config[project_name]["traits"]["trait_algorithm"]

    # generate
    if trait_algorithm == "basic":
        generate_metadata_project_basic(
            config=config, project_name=project_name, overwrite=overwrite
        )
    elif trait_algorithm == "combo":
        metadatas = tt.generate_metadatas_combo(0, num_tokens)
    elif trait_algorithm == "csv":
        metadatas = tt.generate_metadatas_csv(0, num_tokens)
    else:
        raise ValueError(f"invalid {trait_algorithm}")

    if trait_algorithm in ["combo", "csv"]:
        tt.save_metadatas(metadatas=metadatas, overwrite=overwrite)


def validate_project(config, project_name):
    # paths
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
    metadata_fdpath = os.path.join(project_fdpath, "metadata")
    images_fdpath = os.path.join(project_fdpath, "images")
    assets_fdpath = os.path.join(project_fdpath, "assets")

    # settings
    s = config[project_name]["settings"]
    num_tokens = s["num_tokens"]
    try:
        image_format = s["image_format"]
    except KeyError:
        image_format = "png"

    # checks
    failures = {}
    rarity = {}
    success = True

    # images
    for token_num in range(0, num_tokens):
        image_fpath = os.path.join(assets_fdpath, f"{token_num}.{image_format}")

        # image exists
        if not os.path.exists(image_fpath):
            failures.setdefault("missing_images", [])
            failures["missing_images"].append(token_num)
            success = False

    # metadata
    for token_num in range(0, num_tokens):
        metadata_fpath = os.path.join(assets_fdpath, f"{token_num}.json")

        try:
            with open(metadata_fpath, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except FileNotFoundError:
            # metadata exists
            failures.setdefault("missing_metadatas", [])
            failures["missing_metadatas"].append(token_num)
            success = False
        else:
            # attributes rarity
            for attribute in metadata["attributes"]:
                tt = attribute["trait_type"]
                tv = attribute["trait_value"]

                # types
                rarity.setdefault("trait_types", {})
                rarity["trait_types"].setdefault(tt, 0)
                rarity["trait_types"][tt] += 1

                # values
                rarity.setdefault("trait_values", {})
                rarity["trait_values"].setdefault(tv, 0)
                rarity["trait_values"][tv] += 1

    # check rarity
    try:
        min_rarity_basis = config[project_name]["validation"]["min_rarity_basis"]
        logger.info(f"{min_rarity_basis=}")
    except KeyError:
        pass
    else:
        for value_name, value_counts in rarity["trait_values"].items():
            rarity_basis = int(10000 * value_counts / num_tokens)
            logger.debug(
                f"{value_name} ({value_counts}/{num_tokens}) -> {rarity_basis=}"
            )
            if rarity_basis < min_rarity_basis:
                failures.setdefault("low_rarity", [])
                failures["low_rarity"].append(value_name)
                success = False

    # check missing value
    translation = load_csv_map(
        config=config, project_name=project_name, fdname="translations"
    )
    trait_algorithm = config[project_name]["traits"]["trait_algorithm"]
    trait_values = config[project_name]["traits"]["trait_values"]
    expected_values = []
    if trait_algorithm == "combo":
        logger.info(f"checking missing values for {trait_algorithm=}")
        for level1_name, level2_blob in trait_values.items():
            for level2_name, level3_blob in trait_values[level1_name].items():
                logger.debug(f"level3_blob {pformat(level3_blob)}")
                level_expected_values = list(level3_blob.keys())
                expected_values.extend(level_expected_values)
        raw_expected_values = list(set(expected_values))
        if not translation:
            expected_values = raw_expected_values
        else:
            expected_values = [translation[k] for k in raw_expected_values]

        logger.info(f"num expected values: {len(expected_values)}")

        for ev in expected_values:
            if ev not in rarity["trait_values"].keys():
                failures.setdefault("missing_values", [])
                failures["missing_values"].append(ev)
                logger.error(f"missing value {ev}")
                success = False

    else:
        logger.warning(f"missing values check unsupported for {trait_algorithm=}")

    # results
    if not success:
        logger.error(pformat(failures))
        logger.error(f"FAILED validation for {project_name}")
    else:
        logger.info(f"SUCCESS validated {project_name}")

    return success


def generate_images_project(config, project_name, overwrite=False):
    trait_algorithm = config[project_name]["traits"]["trait_algorithm"]
    if trait_algorithm == "basic":
        generate_images_project_basic(
            config=config, project_name=project_name, overwrite=overwrite
        )
    elif trait_algorithm == "combo":
        generate_images_project_combo(
            config=config, project_name=project_name, overwrite=overwrite
        )
    else:
        raise ValueError(f"invalid {trait_algorithm=}")


def generate_images_project_combo(config, project_name, overwrite=False):
    tt = TokenTool(config=config, project_name=project_name)
    project_fdpath = get_project_fdpath(config=config, project_name=project_name)
    input_fdpath = os.path.join(project_fdpath, "metadata")

    # sort metadata input_fnames as numeric and not str, so 0,1,2,3 instead of 0,10,11,12
    input_fnames = os.listdir(input_fdpath)
    input_fnames = [x for x in input_fnames if ".json" in x]
    input_fnames.sort(key=lambda f: int(re.sub("\D", "", f)))
    logger.info(f"found {len(input_fnames)} files")

    metadatas = []
    for input_fname in input_fnames:
        logger.info(f"{input_fname} ->")
        input_fpath = os.path.join(input_fdpath, input_fname)
        with open(input_fpath, "r", encoding="utf-8") as f:
            input_payload = json.load(f)
        metadatas.append(input_payload)

    image_plans = tt.create_image_plans(metadatas=metadatas)
    tt.save_image_plans(image_plans=image_plans, overwrite=overwrite)


def apply_translation(metadata, translation=None, handle_missing="fail"):
    """
    Args:
        metadata (dict): metadata
        translations (optional, dict): key=unique image name, value=translated.
        handle_missing (str): method to handle failures
            - fail: fail on missing
            - None: skip missing

    Returns:
        dict: metadata with trait_values translated
    """
    if not translation:
        return metadata

    new_metadata = copy.deepcopy(metadata)
    for attribute in new_metadata["attributes"]:
        k = attribute["trait_value"]
        try:
            attribute["trait_value"] = translation[k].strip()
        except KeyError:
            if handle_missing is None:
                continue
            elif handle_missing == "fail":
                raise ValueError(f"translation is missing translation for {k}")
            else:
                raise ValueError(f"invalid {handle_missing=}")
    return new_metadata


def apply_media_host(metadata, media_host=None, handle_missing="fail"):
    """
    Args:
        metadata (dict): metadata
        media_hosts (optional, dict): key=unique image name, value=translated.
        handle_missing (str): method to handle failures
            - fail: fail on missing
            - None: skip missing

    Returns:
        dict: metadata with trait_values translated
    """
    if not media_host:
        return metadata

    new_metadata = copy.deepcopy(metadata)
    fname = new_metadata["image"]
    try:
        new_metadata["image"] = media_host[fname]
    except KeyError:
        if handle_missing == "fail":
            raise ValueError(f"missing {fname} in media_host")
        elif handle_missing is None:
            return metadata
        else:
            raise ValueError(f"invalid {handle_missing=}")

    if len(new_metadata["properties"]["files"]) != 1:
        raise ValueError(f"invalid number of files for media host translation")

    new_metadata["properties"]["files"][0]["uri"] = media_host[fname]
    return new_metadata
