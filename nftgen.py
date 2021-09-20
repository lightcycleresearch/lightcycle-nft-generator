#!/usr/bin/env python3
from datetime import datetime, timezone
from shutil import copyfile
import json
import os
import re
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
        "--react-env-candy-machine-id",
        action="store",
        help="candy machine address from 'metaplex create_candy_machine'",
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
        su.initialize_project_folder(config=config, project_name=args.project)

    # generate
    # --------
    if args.generate_metadata:
        su.generate_metadata_project(
            config=config, project_name=args.project, overwrite=args.overwrite
        )

    # images
    # ------

    if args.generate_images:
        su.generate_images_project(
            config=config, project_name=args.project, overwrite=args.overwrite
        )

    # assets
    # ------
    if args.combine_assets:
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

    if args.react_env:
        react_env_dict = {}

        if not args.react_env_candy_machine_id:
            raise ValueError("--react-env-candy-machine-id required")
        react_env_dict["REACT_APP_CANDY_MACHINE_ID"] = args.react_env_candy_machine_id

        # devnet/mainnet
        if args.env == "devnet":
            react_env_dict[
                "REACT_APP_SOLANA_RPC_HOST"
            ] = "https://explorer-api.devnet.solana.com"
        elif args.env == "mainnet-beta":
            react_env_dict[
                "REACT_APP_SOLANA_RPC_HOST"
            ] = "https://api.mainnet-beta.solana.com"
        else:
            raise NotImplementedError
        react_env_dict["REACT_APP_SOLANA_NETWORK"] = args.env

        # program config
        fname = f"{args.env}-temp"
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
