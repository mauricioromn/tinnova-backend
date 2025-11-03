from pydantic import BaseModel
from typing import List, Optional

class ItemBase(BaseModel):
    descripcion: str
    cantidad: int
    precio_unitario: float
    precio_total: float


class ItemCreate(ItemBase):
    pass


class Item(ItemBase):
    id: int
    class Config:
        from_attributes = True


class CotizacionBase(BaseModel):
    proforma: str
    empresa: str
    fecha: str
    atencion: Optional[str] = None
    condiciones: Optional[str] = None


class CotizacionCreate(CotizacionBase):
    items: List[ItemCreate] = []


class Cotizacion(CotizacionBase):
    id: int
    items: List[Item] = []

    class Config:
        from_attributes = True


