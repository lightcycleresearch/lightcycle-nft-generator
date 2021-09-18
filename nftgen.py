#!/usr/bin/env python3
from datetime import datetime, timezone
from shutil import copyfile
import json
import os
import sys

# third-party
from PIL import Image
import yaml

# utils
import src.utils as su

# logging
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def make_args():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--env", action="store", help="default: devnet")
    parser.add_argument(
        "-p", "--project", action="store", help="project name, default is 'example'"
    )
    parser.add_argument(
        "-c",
        "--config",
        action="store",
        help="full path to config file, default is 'config.ini'",
    )
    parser.add_argument(
        "--initialize", action="store_true", help="initialize project directories"
    )
    parser.add_argument(
        "--generate-metadata",
        action="store_true",
        help="generate metadata from example template",
    )
    parser.add_argument(
        "--generate-images",
        action="store_true",
        help="generate imates from traits",
    )
    parser.add_argument(
        "--combine-assets", action="store_true", help="images and metadata into assets"
    )
    parser.add_argument(
        "--overwrite", action="store_true", help="allow overwriting metadata"
    )
    parser.add_argument(
        "--react-env", action="store_true", help="frontend env to stdout"
    )
    parser.add_argument(
        "--react-env-start-date",
        action="store",
        help="default is now, format is: 'DD MMM YYYY HH:MM:SS GMT'",
    )
    parser.add_argument(
        "--override-treasury-address",
        action="store",
        metavar="KEYPAIR",
        help="override treasury address to use keypair instead of creator address",
    )
    parser.set_defaults(project="example", env="devnet")
    args = parser.parse_args()
    return args


def main():
    args = make_args()
    if args.debug:
        logger.setLevel(logging.DEBUG)

    # config
    # ------
    if not args.config:
        config_fpath = os.path.join(BASE_DIR, "config.yaml")
    else:
        config_fpath = args.config
    logger.info(f"Using config: {config_fpath}")

    with open(config_fpath, "r", encoding="utf-8") as f:
        config = yaml.load(f, Loader=yaml.FullLoader)
    su.validate_config(config=config, project_name=args.project)

    # validation
    # ----------
    project_fdpath = os.path.join(BASE_DIR, "projects", args.project)

    # parse config
    # ------------
    project_name = args.project
    settings = config[project_name]["settings"]
    num_tokens = int(settings["num_tokens"])
    creator_address = settings["address"]
    name_prefix = settings["name_prefix"]
    description = settings["description"]
    symbol = settings["symbol"]
    collection = settings["collection"]
    seller_fee_basis_points = int(settings["seller_fee_basis_points"])
    logger.debug(config[project_name]["traits"])

    # folders
    metadata_fdpath = os.path.join(BASE_DIR, "projects", project_name, "metadata")
    images_fdpath = os.path.join(BASE_DIR, "projects", project_name, "images")
    assets_fdpath = os.path.join(BASE_DIR, "projects", project_name, "assets")

    # initialize
    # ----------
    if args.initialize:
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
                trait_restrictions = config[project_name]["traits"][
                    "trait_restrictions"
                ]
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
                trait_type_restrictions = config[project_name]["traits"][
                    "trait_values"
                ][trait_type].keys()
                for trait_type_restriction in trait_type_restrictions:
                    trait_fdpath = os.path.join(
                        trait_type_fdpath, trait_type_restriction
                    )
                    try:
                        os.makedirs(trait_fdpath)
                    except FileExistsError:
                        pass
        logger.info(f"DONE!  Please place your images in {project_fdpath}/traits")

    # generate
    # --------
    if args.generate_metadata:

        logger.info(f"Generating metadata for {num_tokens}")
        TEMPLATE = {
            "attributes": [
                # {"trait_type": "color", "value": "white"},
                # {"trait_type": "pattern", "value": "random"},
            ],
            "collection": collection,
            "description": description,
            "image": None,
            "name": f"{name_prefix} #0",
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
            logger.info(f"Generating metadata for token {token_num} -> {metadata}")
            metadata["attributes"] = su.generate_random_attributes(
                traits=config[project_name]["traits"]
            )

            metadata_fname = f"{token_num}.json"
            metadata_fpath = os.path.join(project_fdpath, "metadata", metadata_fname)
            if os.path.exists(metadata_fpath) and not args.overwrite:
                logger.warning(
                    f"Already exists. You must pass --overwrite to overwrite"
                )
                continue

            logger.info(f"Creating {metadata_fpath}")
            with open(metadata_fpath, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4)

    # images
    # ------

    if args.generate_images:
        traits_fdpath = os.path.join(BASE_DIR, "projects", project_name, "traits")
        fnames = os.listdir(metadata_fdpath)
        fnames = [x for x in fnames if ".json" in x]
        fnames.sort()
        num_tokens = settings["num_tokens"]
        if len(fnames) != num_tokens:
            logger.error(f"🔴invalid number of files in metadata, need {num_tokens}")
            sys.exit(1)

        for i, fname in enumerate(fnames):
            assert i == int(fname.split(".")[0])

            dest_img_fpath = os.path.join(images_fdpath, f"{i}.png")
            if os.path.exists(dest_img_fpath) and not args.overwrite:
                logger.warning(
                    f"Already exists. You must pass --overwrite to overwrite"
                )
                continue

            logger.info(f"{i:05} \t Generating image from {fname}")
            fpath = os.path.join(metadata_fdpath, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                payload = json.load(f)
            flattened = su.flatten_nft_attributes(payload["attributes"])
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
                    source_img_fpath = os.path.join(
                        traits_fdpath, ttype, source_img_fname
                    )
                elif restrictions and ttype not in restrictions:
                    restriction_fdname = flattened[restrictions[0]]
                    source_img_fpath = os.path.join(
                        traits_fdpath, ttype, restriction_fdname, source_img_fname
                    )
                else:
                    source_img_fpath = os.path.join(
                        traits_fdpath, ttype, source_img_fname
                    )
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

    # assets
    # ------
    if args.combine_assets:
        try:
            os.makedirs(assets_fdpath)
        except FileExistsError:
            pass

        for token_num in range(0, num_tokens):
            logger.info(f"Combining assets for {token_num}")

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
                    f"Already exists. You must pass --overwrite to overwrite"
                )
                continue

            # copy to assets
            copyfile(image_source, image_dest)
            copyfile(metadata_source, metadata_dest)

    if args.react_env:

        react_env_dict = {}

        # devnet/mainnet
        if args.env == "devnet":
            fname = "devnet-temp"
            react_env_dict[
                "REACT_APP_SOLANA_RPC_HOST"
            ] = "https://explorer-api.devnet.solana.com"
        else:
            raise NotImplementedError
        react_env_dict["REACT_APP_SOLANA_NETWORK"] = args.env

        # program config
        fpath = os.path.join(project_fdpath, ".cache", fname)
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except FileNotFoundError:
            logger.error(f"🔴You do not have a cache: {fpath}")
            sys.exit()
        else:
            program_config = su.program_config_from_cache(payload)
            react_env_dict["REACT_APP_CANDY_MACHINE_CONFIG"] = program_config

        # candy machine ID
        react_env_dict["REACT_APP_CANDY_MACHINE_ID"] = "REPLACEME"

        # start date
        if args.react_env_start_date:
            react_env_dict["REACT_APP_CANDY_START_DATE"] = su.start_date_to_timestamp(
                args.react_env_start_date
            )
        else:
            now = datetime.now(timezone.utc)
            logger.info(f"using timestamp: {now.isoformat()=}")
            react_env_dict["REACT_APP_CANDY_START_DATE"] = int(now.timestamp())

        # treasury
        if args.override_treasury_address:
            pubkey = su.solana_keygen_pubkey(args.override_treasury_address)
            logger.info(f"overriding creator {creator_address} with {pubkey}")
            react_env_dict["REACT_APP_TREASURY_ADDRESS"] = pubkey
        else:
            react_env_dict["REACT_APP_TREASURY_ADDRESS"] = creator_address

        # stdout
        for k, v in react_env_dict.items():
            print(f"{k}={v}")


if __name__ == "__main__":
    main()
