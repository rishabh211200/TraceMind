"""Common API schemas for pagination and meta envelopes."""

from pydantic import BaseModel, Field


class PaginationMeta(BaseModel):
    """Pagination metadata model."""

    total: int = Field(description="Total count of items matching filter criteria")
    limit: int = Field(description="Maximum items per page")
    offset: int = Field(description="Offset index for pagination")
    has_more: bool = Field(description="Whether more records are available")


class PaginatedResponse[T](BaseModel):
    """Standardized paginated list container."""

    items: list[T] = Field(description="List of records for current page")
    pagination: PaginationMeta = Field(description="Pagination cursor metadata")
