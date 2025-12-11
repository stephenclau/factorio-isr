#!/bin/bash
set -euo pipefail

function tz () {
echo "****************************************************************************";
#Default timezone to America/Vancouver
if [ -n "${TZ:-America/Vancouver}" ]; then
    echo "Setting timezone to ${TZ}"
    ln -snf "/usr/share/zoneinfo/${TZ}" /etc/localtime
    echo "${TZ}" > /etc/timezone
fi
}
function main() {
echo "****************************************************************************";
groupmod -g ${GID} factorio-isr \
&& usermod -u ${UID} -g ${GID} factorio-isr
echo "Aligning container directory permissions to the host user UID:GID ${UID}:${GID}..."
chown -R "${UID}:${GID}" /app 2>/dev/null || true
echo "Permissions aligned."
echo "****************************************************************************";
echo "Starting FISR..."
if [ $# -gt 0 ]; then
    exec gosu factorio-isr "$@"
else
    exec gosu factorio-isr python -m src.main
fi
echo "****************************************************************************";
echo "FISR Running."
}

# script execution
tz
main