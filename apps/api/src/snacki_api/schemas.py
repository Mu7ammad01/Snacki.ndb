"""Formats d'entrée et de sortie de l'API (Pydantic).

On ne renvoie jamais un objet de la base tel quel : chaque réponse liste ses champs (ASVS V15.3.1).
"""

import re
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from snacki_api.models import Badge, Category, Fulfilment, OrderStatus


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    category: Category
    name_fr: str
    name_ar: str
    description_fr: str
    description_ar: str
    price_mru: int
    badge: Badge | None
    photo: str | None


class MenuOut(BaseModel):
    currency: str = "MRU"
    products: list[ProductOut]


class Health(BaseModel):
    status: str


# --- Commandes (J3) -------------------------------------------------------------------------
# Validation positive (ASVS V2.2.1) : chaque champ a un format autorisé, tout le reste est refusé.
# `extra="forbid"` : un champ inattendu (« price », « total »…) rend la requête invalide (T01).

_NO_CONTROL = r"^[^\x00-\x1f\x7f]+$"
Name = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40, pattern=_NO_CONTROL)
]
Landmark = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=3, max_length=120, pattern=_NO_CONTROL)
]
ProductRef = Annotated[str, StringConstraints(pattern=r"^[a-z][a-z-]{0,39}$")]


class OrderItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: ProductRef
    quantity: int = Field(ge=1, le=20)


class OrderIn(BaseModel):
    """Ce que le client envoie : des produits et des quantités, jamais un prix ni un total."""

    model_config = ConfigDict(extra="forbid")

    customer_name: Name
    phone: str = Field(description="Mobile mauritanien : 8 chiffres commençant par 2, 3 ou 4")
    fulfilment: Fulfilment
    landmark: Landmark | None = None
    items: list[OrderItemIn] = Field(min_length=1, max_length=10)

    @field_validator("phone")
    @classmethod
    def _phone_mr(cls, value: str) -> str:
        digits = re.sub(r"[\s.-]", "", value)
        for prefix in ("+222", "00222"):
            if digits.startswith(prefix):
                digits = digits[len(prefix) :]
        if not re.fullmatch(r"[234][0-9]{7}", digits):
            raise ValueError("numéro mauritanien attendu : 8 chiffres commençant par 2, 3 ou 4")
        return digits

    @model_validator(mode="after")
    def _coherence(self) -> "OrderIn":
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("un produit ne doit apparaître qu'une fois (regrouper les quantités)")
        if self.fulfilment is Fulfilment.LIVRAISON and self.landmark is None:
            raise ValueError("un repère est obligatoire pour une livraison")
        return self


class OrderLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_id: str
    quantity: int
    unit_price_mru: int
    line_total_mru: int


class OrderTrackOut(BaseModel):
    """Suivi public : aucune donnée personnelle (ni prénom, ni téléphone, ni repère) (T03)."""

    model_config = ConfigDict(from_attributes=True)

    number: str
    status: OrderStatus
    fulfilment: Fulfilment
    total_mru: int
    currency: str = "MRU"
    lines: list[OrderLineOut]
    created_at: datetime


class OrderCreatedOut(OrderTrackOut):
    # Renvoyé une seule fois, à la création : l'API n'en garde que l'empreinte.
    tracking_token: str
    tracking_expires_at: datetime
