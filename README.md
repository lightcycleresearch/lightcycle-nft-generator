# lightcycle-nft-generator

Generate NFTs with metaplex standard

## INSTALL

1. Create venv 
	```
	make venv
	```
2. Activate venv
	```
	source venv/bin/activate
	```
3. Install requirements
	```
	pip install -r requirements.txt
	```

## DEVELOP

1. To run tests:
	```
	pip install -r requirements-dev.txt
	```
2. Run tests
	```
	pytest
	```

## USAGE

1. Create config.ini end change `REPLACEME` with your address
	```
	cp config.yaml.example config.yaml
	```
2. Initialize project
	```
	nftgen.py --project example --config config.yaml --initialize
	```
3. Add your images to the projects/example/traits/ folders that were created by the previous command
4. Generate metadata
	```
	nftgen.py --project example --config config.yaml --generate-metadata
	```
4. Generate images from metadata
	```
	nftgen.py --project example --config config.yaml --generate-images
	```
4. Combine assets, which copies the images and metadata into one folder
	```
	nftgen.py --project example --config config.yaml --combine-assets
	```

You must have `solana-keygen` available if you want to generate the environment automatically:

4. Create react env for frontend
	```
	nftgen.py --project example --config config.yaml --react-env --react-env-start-date "01 Jan 31 12:00:00 GMT" --react-env-keypair ~/.config/solana/devnet-lightcycle.json
	```
Note: there is a Makefile for convenience, update the environmental variables before using
