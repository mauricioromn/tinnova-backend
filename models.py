from sqlalchemy import Column, Integer, String, Float, ForeignKey
from sqlalchemy.orm import relationship
from database import Base

class Cotizacion(Base):
    __tablename__ = "cotizaciones"

    id = Column(Integer, primary_key=True, index=True)
    proforma = Column(String, index=True)
    empresa = Column(String)
    fecha = Column(String)
    atencion = Column(String, nullable=True)
    condiciones = Column(String, nullable=True)

    items = relationship("Item", back_populates="cotizacion", cascade="all, delete")


class Item(Base):
    __tablename__ = "items"

    id = Column(Integer, primary_key=True, index=True)
    cotizacion_id = Column(Integer, ForeignKey("cotizaciones.id"))
    descripcion = Column(String)
    cantidad = Column(Integer)
    precio_unitario = Column(Float)
    precio_total = Column(Float)

    cotizacion = relationship("Cotizacion", back_populates="items")

