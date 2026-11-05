"""Hlídá závislosti potřebné v produkčním kontejneru (chybějící WebSocket knihovna tiše rozbije živý přehled)."""
import os

REQ = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "requirements.txt")


def test_production_requirements():
    text = open(REQ).read()
    assert "uvicorn[standard]" in text  # websockets/httptools pro WebSocket upgrade
    assert "psycopg[binary]" in text  # ovladač pro PostgreSQL
    assert "alembic" in text  # migrace při startu kontejneru
