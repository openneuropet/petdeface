# this makefile allows for some prepacking steps and other quality of life fixes
# for this repo

# make build activates poetry build after copying over dockerfile and pyproject.toml to petdeface dir
build:
	cp Dockerfile petdeface/
	cp pyproject.toml petdeface/
	cp README.md petdeface/
	poetry build

# make publish runs the above make build command, then pushs the most recent build to pypi
publish: build
	poetry publish
