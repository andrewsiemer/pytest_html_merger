NAME=pytest_html_merger

.PHONY: build upload dist check docs major _major minor _minor patch _patch rc _rc _build

build: check

_build: clean
	@echo "Publishing"
	vmn show ${EXTRA_SHOW_ARGS} --verbose pytest_html_merger > src/ver.yml
	python3 ${PWD}/gen_ver.py
	python3 setup.py sdist bdist_wheel
	git checkout -- ${PWD}/src/version.py

upload:
	twine upload ${PWD}/dist/*

major: check _major _build

_major:
	@echo "Major Release"
	vmn stamp -r major ${NAME}

minor: check _minor _build

_minor:
	@echo "Minor Release"
	vmn stamp -r minor ${NAME}

patch: check _patch _build

_patch:
	@echo "Patch Release"
	vmn stamp -r patch ${NAME}

rc: check _rc _build

_rc:
	@echo "RC Release"
	vmn stamp ${NAME}
	$(eval EXTRA_SHOW_ARGS := --template [{major}][.{minor}][.{patch}][{prerelease}])

check:
	@echo "-------------------------------------------------------------"
	@echo "-------------------------------------------------------------"
	@echo "-~      Running static checks                              --"
	@echo "-------------------------------------------------------------"
	black ${PWD}
	@echo "-~      Running unit tests                                 --"
	@echo "-------------------------------------------------------------"
	@echo "-------------------------------------------------------------"
	@echo "-------------------------------------------------------------"

clean:
	git checkout -- ${PWD}/src/version.py
	rm -rf ${PWD}/dist
	rm -rf ${PWD}/build
