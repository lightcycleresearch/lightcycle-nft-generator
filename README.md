# lightcycle-nft-generator

Generate NFTs with metaplex standard

## USAGE

1. Create config.ini end change `REPLACEME` with your address
	```
	cp config.ini.example config.ini
	```
2. Initialize project
	```
	python nftgen.py --project example --config config.ini --initialize
	```
3. Add your images to the projects/example/images/ folder.  In the examples, we've included two
4. Generate metadata
	```
	python nftgen.py --project example --config config.ini --generate-metadata
	```
4. Generate assets, which moves the images and metadata into one folder
	```
	python nftgen.py --project example --config config.ini --generate-assets
	```
