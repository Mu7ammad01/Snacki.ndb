"""Formats d'entrée et de sortie de l'API (Pydantic).

On ne renvoie jamais un objet de la base tel quel : chaque réponse liste ses champs (ASVS V15.3.1).
"""

from pydantic import BaseModel, ConfigDict

from snacki_api.models import Badge, Category


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
