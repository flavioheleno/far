.DEFAULT_GOAL := help

ROOT := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
PYTHON ?= python3
PACKAGES ?=
UPDATE_FLAGS ?=
REPORT ?= .far-updates/report.json

.PHONY: help check test lint validate list update update-apply report srcinfo

help:
	@printf '%s\n' \
	  'FAR maintenance commands:' \
	  '  make check          Check recipes and generated metadata' \
	  '  make test           Run offline unit tests' \
	  '  make lint           Check GitHub Actions workflows with actionlint' \
	  '  make validate       Run check, test, and lint' \
	  '  make list           List managed packages' \
	  '  make update         Preview upstream updates (uses the network)' \
	  '  make update-apply   Apply upstream updates to recipes and metadata' \
	  '  make report         Preview updates and write a JSON report' \
	  '  make srcinfo PACKAGE=<pkgbase>  Regenerate one package metadata file' \
	  '' \
	  'Options:' \
	  '  PACKAGES="pkgbase ..."  Limit checks and updates (default: all)' \
	  '  UPDATE_FLAGS="..."      Extra updater options, e.g. --verify-current' \
	  '  REPORT=<path>           Report path (default: .far-updates/report.json)' \
	  'Relative paths are resolved from the repository root.'

check:
	cd "$(ROOT)" && ./scripts/check-packages $(PACKAGES)

test:
	cd "$(ROOT)" && $(PYTHON) -m unittest discover -s tests -v

lint:
	cd "$(ROOT)" && actionlint

validate: check test lint

list:
	cd "$(ROOT)" && ./scripts/update-packages --list

update:
	cd "$(ROOT)" && ./scripts/update-packages $(UPDATE_FLAGS) $(PACKAGES)

update-apply:
	cd "$(ROOT)" && ./scripts/update-packages --apply $(UPDATE_FLAGS) $(PACKAGES)

report:
	cd "$(ROOT)" && mkdir -p "$$(dirname -- "$(REPORT)")" && \
	  ./scripts/update-packages --report "$(REPORT)" $(UPDATE_FLAGS) $(PACKAGES)

srcinfo:
	@test -n "$(PACKAGE)" || { echo 'Usage: make srcinfo PACKAGE=<pkgbase>' >&2; exit 1; }
	@cd "$(ROOT)" && \
	  temporary=$$(mktemp .SRCINFO.XXXXXX) && \
	  trap 'rm -f "$$temporary"' EXIT HUP INT TERM && \
	  $(PYTHON) -c 'import sys; sys.path.insert(0, "scripts"); from far import cli, generate_srcinfo, package_paths; cli(lambda: print(generate_srcinfo(package_paths([sys.argv[1]])[0]), end=""))' "$(PACKAGE)" > "$$temporary" && \
	  chmod 644 "$$temporary" && mv -- "$$temporary" "packages/$(PACKAGE)/.SRCINFO"
