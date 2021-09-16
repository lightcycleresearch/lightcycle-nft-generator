#!/usr/bin/env python3
from shutil import copyfile
import configparser
import json
import os
import sys


# logging
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = os.path.dirname(os.path.realpath(__file__))


def make_args():
    import argparse

    parser = argparse.ArgumentParser()
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
        "--overwrite-metadata", action="store_true", help="allow overwriting metadata"
    )
    parser.add_argument(
        "--generate-assets", action="store_true", help="images and metadata into assets"
    )
    parser.set_defaults(project="example")
    args = parser.parse_args()
    return args


def validate_config(config, project_name):
    sections = config.sections()
    if not sections:
        logger.error(
            f"Please ensure projects exist in config. Maybe: \n\t cp config.ini.example config.ini"
        )
        sys.exit(1)

    project_creator_address = config[project_name]["properties.creators.address"]
    logger.info(
        f"creator address for project '{project_name}' is '{project_creator_address}'"
    )
    if project_creator_address == "REPLACEME":
        logger.error(f"Please replace properties.creator.address in {config_fpath}")
        sys.exit(1)


def main():
    args = make_args()

    # config
    # ------
    if not args.config:
        config_fpath = os.path.join(BASE_DIR, "config.ini")
    else:
        config_fpath = args.config
    logger.info(f"Using config: {config_fpath}")

    config = configparser.ConfigParser()
    config.read(config_fpath)
    validate_config(config=config, project_name=args.project)

    # validation
    # ----------
    project_fdpath = os.path.join(BASE_DIR, "projects", args.project)

    if os.path.exists(os.path.join(project_fdpath, ".cache")):
        logger.error(
            f"You already have a .cache directory for {args.project}.  Delete it if you know what you're doing."
        )
        sys.exit()

    # parse config
    # ------------
    project_name = args.project
    num_tokens = int(config[project_name]["num_tokens"])
    creator_address = config[project_name]["properties.creators.address"]
    name_prefix = config[project_name]["name_prefix"]
    description = config[project_name]["description"]
    symbol = config[project_name]["symbol"]
    collection = config[project_name]["collection"]
    seller_fee_basis_points = int(config[project_name]["seller_fee_basis_points"])

    # initialize
    # ----------
    if args.initialize:
        logger.info(f"Initializing {project_fdpath} folders")
        try:
            os.makedirs(os.path.join(project_fdpath, "metadata"))
        except FileExistsError:
            pass

        try:
            os.makedirs(os.path.join(project_fdpath, "images"))
        except FileExistsError:
            pass

        logger.info(f"DONE!  Please place your images in {project_fdpath}/images")

    # generate
    # --------
    if args.generate_metadata:

        logger.info(f"Generating metadata for {num_tokens}")
        TEMPLATE = {
            # TODO: fix HARDCODE attributes for example only
            "attributes": [
                {"trait_type": "color", "value": "white"},
                {"trait_type": "pattern", "value": "random"},
            ],
            "collection": collection,
            "description": description,
            "image": "0.png",
            "name": f"{name_prefix} #0",
            "properties": {
                "category": "image",
                "creators": [
                    {
                        "address": creator_address,
                        "share": 100,
                    }
                ],
                "files": [{"type": "image/png", "uri": "0.png"}],
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
            logger.info(f"Generating metadta for token {token_num} -> {metadata}")

            metadata_fname = f"{token_num}.json"
            metadata_fpath = os.path.join(project_fdpath, "metadata", metadata_fname)
            if os.path.exists(metadata_fpath) and not args.overwrite_metadata:
                logger.error(
                    f"Already exists. You must pass --overwrite-metadata to overwrite"
                )
                sys.exit(1)

            logger.info(f"Creating {metadata_fpath}")
            with open(metadata_fpath, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=4)

    # assets
    # ------
    if args.generate_assets:
        images_fdpath = os.path.join(BASE_DIR, "projects", project_name, "images")
        metadata_fdpath = os.path.join(BASE_DIR, "projects", project_name, "metadata")
        assets_fdpath = os.path.join(BASE_DIR, "projects", project_name, "assets")
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

            # copy to assets
            copyfile(image_source, os.path.join(assets_fdpath, image_fname))
            copyfile(metadata_source, os.path.join(assets_fdpath, metadata_fname))


if __name__ == "__main__":
    main()
