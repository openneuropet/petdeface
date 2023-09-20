# Quickly run black on all python files in this repository, local version of the pre-commit hook
black:
	for file in `find . -name "*.py"`; do \
		black $$file; \
	done

testlayouts:
	pytest tests/test_dir_layouts.py -s -vv

# run all tests
testall: testlayouts
.PHONY: testall

# install python dependencies
pythondeps:
	pip install --upgrade pip && pip install  -e . && pip install -e .[dev]