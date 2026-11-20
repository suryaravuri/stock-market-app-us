from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.market.sessions import INDIAN_SUFFIXES, validate_indian_symbol


class StockBase(BaseModel):
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=20
    )

    company_name: str | None = Field(
        default=None,
        max_length=255
    )

    exchange: str | None = Field(
        default=None,
        max_length=30
    )

    asset_type: str = Field(
        default="STOCK",
        max_length=30
    )

    sector: str | None = Field(
        default=None,
        max_length=100
    )

    industry: str | None = Field(
        default=None,
        max_length=150
    )

    tradable: bool = True
    active: bool = True

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("exchange", "asset_type")
    @classmethod
    def normalize_uppercase_fields(
            cls,
            value: str | None
    ) -> str | None:
        if value is None:
            return None

        return value.strip().upper()


class StockCreate(StockBase):

    @model_validator(mode="after")
    def check_indian_listing(self):
        # RELIANCE.NS with no exchange -> exchange NSE (and .BO -> BSE).
        if not self.exchange:
            for suffix, exchange in INDIAN_SUFFIXES.items():
                if self.symbol.endswith(suffix):
                    self.exchange = exchange
        error = validate_indian_symbol(self.symbol, self.exchange)
        if error:
            raise ValueError(error)
        return self


class StockUpdate(BaseModel):
    company_name: str | None = Field(
        default=None,
        max_length=255
    )

    exchange: str | None = Field(
        default=None,
        max_length=30
    )

    asset_type: str | None = Field(
        default=None,
        max_length=30
    )

    sector: str | None = Field(
        default=None,
        max_length=100
    )

    industry: str | None = Field(
        default=None,
        max_length=150
    )

    tradable: bool | None = None
    active: bool | None = None

    @field_validator("exchange", "asset_type")
    @classmethod
    def normalize_uppercase_fields(
            cls,
            value: str | None
    ) -> str | None:
        if value is None:
            return None

        return value.strip().upper()


class StockResponse(StockBase):
    stock_id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(
        from_attributes=True
    )


class StockBulkCreate(BaseModel):
    stocks: list[StockCreate] = Field(
        ...,
        min_length=1,
        max_length=5000,
    )


class StockBulkError(BaseModel):
    row: int
    symbol: str | None = None
    message: str


class StockBulkResponse(BaseModel):
    total: int
    inserted: int
    already_exists: int
    failed: int

    inserted_symbols: list[str] = Field(default_factory=list)
    existing_symbols: list[str] = Field(default_factory=list)
    errors: list[StockBulkError] = Field(default_factory=list)
