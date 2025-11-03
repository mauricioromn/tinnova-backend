from sqlalchemy.orm import Session
import models, schemas

def get_cotizaciones(db: Session, skip: int = 0, limit: int = 100):
    return db.query(models.Cotizacion).offset(skip).limit(limit).all()

def create_cotizacion(db: Session, cotizacion: schemas.CotizacionCreate):
    db_cotizacion = models.Cotizacion(
        proforma=cotizacion.proforma,
        empresa=cotizacion.empresa,
        fecha=cotizacion.fecha,
        atencion=cotizacion.atencion,
        condiciones=cotizacion.condiciones,
    )
    db.add(db_cotizacion)
    db.commit()
    db.refresh(db_cotizacion)

    for item in cotizacion.items:
        db_item = models.Item(
            cotizacion_id=db_cotizacion.id,
            descripcion=item.descripcion,
            cantidad=item.cantidad,
            precio_unitario=item.precio_unitario,
            precio_total=item.precio_total,
        )
        db.add(db_item)

    db.commit()
    db.refresh(db_cotizacion)
    return db_cotizacion

