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
chown -R "${UID}:${GID}" /app
echo "Permissions aligned."
echo "****************************************************************************";
echo "Starting FISR..."
exec gosu factorio-isr "$@"
echo "****************************************************************************";
echo "FISR Running."
}

# script execution
tz
main