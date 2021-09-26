# lightcycle-nft-generator

Generate NFTs with metaplex standard

## INSTALL

1. Create venv 
	```
	 python3 -m venv venv
	```
2. Activate venv
	```
	source venv/bin/activate
	```
3. Install requirements
	```
	pip install -r requirements.txt
	```

### DEVELOP

1. Install development requirements
	```
	pip install -r requirements-dev.txt
	```
2. Run tests
	```
	pytest
	```

## USAGE

1. Create config
	```
	cp config.yaml.example config.yaml
	```
2. Edit config to change `REPLACEME` with your address
	```
	vim config.yaml
	```
3. Initialize project
	```
	nftgen.py --project example --config config.yaml --initialize
	```
4. Add your images to the projects/example/traits/ folders that were created by the previous command
5. Generate metadata
	```
	nftgen.py --project example --config config.yaml --generate-metadata
	```
6. Generate images from metadata
	```
	nftgen.py --project example --config config.yaml --generate-images
	```
7. Validate assets, which checks for minimum rarity and missing values
	```
	nftgen.py --project example --config config.yaml --validate
	```
8. Combine assets, which copies the images and metadata into one folder
	```
	nftgen.py --project example --config config.yaml --combine-assets
	```

You must have `solana-keygen` available if you want to generate the environment automatically:

1. Create react env for frontend
	```
	nftgen.py --project example --config config.yaml --react-env --react-env-start-date "01 Jan 31 12:00:00 GMT" --react-env-keypair ~/.config/solana/devnet-lightcycle.json
	```
Note: there is a Makefile for convenience, update the environmental variables before using

## Experimental

- Add translation csv file, i.e. english.csv, to the translations subdirectory to apply translations via --combine-assets