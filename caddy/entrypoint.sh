#!/bin/sh
set -e
# CADDY_WHITELIST_ENABLED=true → only CADDY_WHITELIST_IPS (space-separated CIDRs) may reach upstreams.
# false → allow all (0.0.0.0/0 ::/0). CADDY_ALLOWED_IPS is what Caddyfile reads.
if [ "${CADDY_WHITELIST_ENABLED}" = "true" ]; then
  if [ -z "${CADDY_WHITELIST_IPS}" ]; then
    echo "caddy: CADDY_WHITELIST_ENABLED=true requires non-empty CADDY_WHITELIST_IPS (space-separated CIDRs, e.g. 203.0.113.0/24 10.0.0.0/8)" >&2
    exit 1
  fi
  export CADDY_ALLOWED_IPS="${CADDY_WHITELIST_IPS}"
else
  export CADDY_ALLOWED_IPS="0.0.0.0/0 ::/0"
fi
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile "$@"
