#!/bin/sh
# Před spuštěním služby aplikuje migrace databáze. Při chybě kontejner skončí.
set -e
alembic upgrade head
exec "$@"
