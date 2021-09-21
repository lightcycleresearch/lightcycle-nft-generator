#!/usr/bin/env python3
import os

# third-party
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
        "--generate-metadata-new",
        action="store_true",
        help="generate metadata from example template",
    )
    parser.add_argument(
        "--generate-images",
        action="store_true",
        help="generate imates from traits",
    )
    parser.add_argument(
        "--generate-images-new",
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

    if args.generate_metadata_new:
        su.generate_metadata_project_new(
            config=config, project_name=args.project, overwrite=args.overwrite
        )

    # images
    # ------

    if args.generate_images:
        su.generate_images_project(
            config=config, project_name=args.project, overwrite=args.overwrite
        )

    if args.generate_images_new:
        su.generate_images_project_new(
            config=config, project_name=args.project, overwrite=args.overwrite
        )

    # assets
    # ------
    if args.combine_assets:
        su.combine_assets_project(
            config=config, project_name=args.project, overwrite=args.overwrite
        )

    # react env for frontend
    # ----------------------
    if args.react_env:
        su.react_env_for_project(
            config=config,
            project_name=args.project,
            react_env_candy_machine_id=args.react_env_candy_machine_id,
            env=args.env,
            react_env_start_date=args.react_env_start_date,
            override_treasury_address=args.override_treasury_address,
        )


if __name__ == "__main__":
    main()
