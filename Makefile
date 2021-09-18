PROJECT=example
CONFIG=config.yaml
STARTDATE=01 Sep 2021 00:00:00 GMT
UIFDPATH=${HOME}/

venv: ## venv
	python3 -m venv venv --prompt lightcycle

requirements: ## install requirements
	pip install -r requirements.txt

test: ## run test
	pytest

autotest: ## run test on changes
	pytest-watch

initialize: ## initialize
	./nftgen.py --config "${CONFIG}" --project "${PROJECT}" --initialize

generate_metadata: initialize ## generate metadata
	./nftgen.py --config "${CONFIG}" --project "${PROJECT}" --generate-metadata

generate_images: generate_metadata ## generate images
	./nftgen.py --config "${CONFIG}" --project "${PROJECT}" --generate-images

combine_assets: generate_images ## combine assets (metadata and images)
	./nftgen.py --config "${CONFIG}" --project "${PROJECT}" --combine-assets

env: ## create env file for react ui, use 'make env > REACT_DIR/.env'
	./nftgen.py --config "${CONFIG}" --project "${PROJECT}" --react-env --react-env-start-date "${STARTDATE}" > ${UIFDPATH}/.env


.PHONY: help

help:
		@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
.DEFAULT_GOAL := help
