"""Typed request, tool, and response models for the Campus Customs chat agent."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StockLevel(BaseModel):
    size: str
    quantity: int


class ProductMatch(BaseModel):
    """A product the catalogue tool found for the shopper's question."""

    product_id: str
    name: str
    garment_type: str
    description: str
    price: float
    image_url: str
    colors: list[str] = Field(default_factory=list)
    stock: list[StockLevel] = Field(default_factory=list)
    total_stock: int = 0


class AgentReply(BaseModel):
    """The model's bounded final answer after it uses any needed tools."""

    reply: str = Field(min_length=1, max_length=4000)
    product_ids: list[str] = Field(default_factory=list, max_length=8)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    page_context: dict[str, Any] = Field(default_factory=dict)


class ChatResponse(BaseModel):
    reply: str
    matches: list[ProductMatch] = Field(default_factory=list, max_length=8)


class ChatHistoryMessage(BaseModel):
    id: int
    role: Literal["user", "assistant"]
    content: str
    matches: list[ProductMatch] = Field(default_factory=list, max_length=8)
    created_at: str


class ChatHistoryResponse(BaseModel):
    messages: list[ChatHistoryMessage]
