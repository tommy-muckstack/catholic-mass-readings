#!/usr/bin/env bash

# Checks all the Python packages.

SCRIPT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
SCRIPT_NAME=$( basename "${BASH_SOURCE[0]}" )
PYTHON_ROOT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )

if ! command -v "poetry" &> /dev/null; then
    exec "${SCRIPT_PATH}/console.sh" "${SCRIPT_PATH}/${SCRIPT_NAME}"
fi

# shellcheck disable=SC2207
PACKAGE_PATHS=($(find "${PYTHON_ROOT_PATH}" -name "pyproject.toml" -exec dirname {} \;))

for PACKAGE_PATH in "${PACKAGE_PATHS[@]}"; do
    PACKAGE_NAME=$(basename "${PACKAGE_PATH}")
    if [ "${PACKAGE_NAME}" != "contact-messenger-bot-api" ]; then
        pushd "${PACKAGE_PATH}" >/dev/null ||  { FAILED+=("${PACKAGE_NAME}"); continue; }
        poetry remove "contact-messenger-bot-api"
        poetry add "../contact-messenger-bot-api"
        popd >/dev/null || { continue; }
    fi
done
