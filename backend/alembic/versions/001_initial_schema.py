"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), unique=True, nullable=False, index=True),
        sa.Column("hashed_password", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("token_hash", sa.String(), unique=True, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked", sa.Boolean(), default=False, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "card_cache",
        sa.Column("card_id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, index=True),
        sa.Column("set_id", sa.String()),
        sa.Column("set_name", sa.String()),
        sa.Column("series", sa.String()),
        sa.Column("number", sa.String()),
        sa.Column("rarity", sa.String()),
        sa.Column("supertype", sa.String()),
        sa.Column("subtypes_json", sa.Text()),
        sa.Column("hp", sa.Integer()),
        sa.Column("types_json", sa.Text()),
        sa.Column("image_url_sm", sa.String()),
        sa.Column("image_url_lg", sa.String()),
        sa.Column("data_json", sa.Text(), nullable=False),
        sa.Column("cached_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "price_cache",
        sa.Column("card_id", sa.String(), primary_key=True),
        sa.Column("market_price", sa.Float()),
        sa.Column("low_price", sa.Float()),
        sa.Column("mid_price", sa.Float()),
        sa.Column("high_price", sa.Float()),
        sa.Column("foil_market", sa.Float()),
        sa.Column("source", sa.String(), default="justtcg"),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("card_id", sa.String(), nullable=False, index=True),
        sa.Column("status", sa.String(), nullable=False, default="holding"),
        sa.Column("condition", sa.String(), nullable=False, default="near_mint"),
        sa.Column("quantity", sa.Integer(), nullable=False, default=1),
        sa.Column("purchase_price", sa.Float()),
        sa.Column("sale_price", sa.Float()),
        sa.Column("market_price_at_scan", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.Column("source_location", sa.String()),
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sold_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("client_id", sa.String(), unique=True),
    )

    op.create_table(
        "transactions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("inventory_item_id", sa.String()),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column("quantity", sa.Integer(), default=1),
        sa.Column("payment_method", sa.String()),
        sa.Column("location", sa.String()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("client_id", sa.String(), unique=True),
    )

    op.create_table(
        "scan_history",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("user_id", sa.String(), nullable=False, index=True),
        sa.Column("card_id", sa.String()),
        sa.Column("raw_ocr_text", sa.Text()),
        sa.Column("confidence_score", sa.Float()),
        sa.Column("pipeline_stage", sa.String()),
        sa.Column("scan_duration_ms", sa.Integer()),
        sa.Column("scanned_at", sa.DateTime(timezone=True), nullable=False),
    )

    # FTS5 virtual table for fuzzy card name search (SQLite only)
    op.execute(
        "CREATE VIRTUAL TABLE IF NOT EXISTS card_fts "
        "USING fts5(card_id UNINDEXED, name, content='card_cache', content_rowid='rowid')"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS card_fts")
    op.drop_table("scan_history")
    op.drop_table("transactions")
    op.drop_table("inventory_items")
    op.drop_table("price_cache")
    op.drop_table("card_cache")
    op.drop_table("refresh_tokens")
    op.drop_table("users")
