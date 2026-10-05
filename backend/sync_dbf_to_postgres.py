import os
from dbfread import DBF
from sqlalchemy import text
from datetime import date, datetime
from database import engine, SessionLocal
import models

def add_columns_safely():
    """
    Agrega las nuevas columnas a la tabla 'clients' si no existen,
    asegurando que la base de datos se actualice sin perder datos existentes.
    """
    print("Iniciando migración segura de columnas en PostgreSQL...")
    columns_to_add = [
        ("codigo", "VARCHAR UNIQUE"),
        ("nombre_fantasia", "VARCHAR"),
        ("cparte", "VARCHAR"),
        ("saldo", "DOUBLE PRECISION DEFAULT 0.0"),
        ("email", "VARCHAR"),
        ("localidad", "VARCHAR"),
        ("fecha_ultimo_pago", "DATE"),
        ("fecha_registro", "DATE"),
        ("vendedor_codigo", "VARCHAR"),
        ("vendedor_nombre", "VARCHAR"),
        ("clasificacion_codigo", "VARCHAR"),
        ("clasificacion_nombre", "VARCHAR"),
        ("extracto", "TEXT"),
        ("cclifac", "VARCHAR")
    ]
    
    with engine.connect() as conn:
        for col_name, col_type in columns_to_add:
            try:
                # Comprobar si la columna ya existe
                check_query = text(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='clients' AND column_name='{col_name}';
                """)
                res = conn.execute(check_query).fetchone()
                if not res:
                    print(f"Agregando columna '{col_name}' ({col_type})...")
                    conn.execute(text(f"ALTER TABLE clients ADD COLUMN {col_name} {col_type};"))
                    conn.commit()
                else:
                    print(f"La columna '{col_name}' ya existe en 'clients'.")
            except Exception as e:
                print(f"Error al agregar columna {col_name}: {e}")
                
        # Asegurarse de que el índice único para el código exista
        try:
            conn.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_clients_codigo ON clients (codigo);"))
            conn.commit()
            print("Índice único para 'codigo' verificado.")
        except Exception as e:
            print(f"Error creando índice de código: {e}")
            
        # Eliminar índice único y restricciones únicas de identificador_fiscal para permitir duplicados (sucursales)
        try:
            print("Verificando y removiendo restricciones únicas de 'identificador_fiscal'...")
            conn.execute(text("DROP INDEX IF EXISTS ix_clients_identificador_fiscal;"))
            conn.execute(text("ALTER TABLE clients DROP CONSTRAINT IF EXISTS clients_identificador_fiscal_key CASCADE;"))
            conn.execute(text("ALTER TABLE clients DROP CONSTRAINT IF EXISTS uq_clients_identificador_fiscal CASCADE;"))
            # Crear índice no único para búsquedas veloces
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_clients_identificador_fiscal ON clients (identificador_fiscal);"))
            conn.commit()
            print("Restricciones de identificador_fiscal actualizadas con éxito.")
        except Exception as e:
            print(f"Error al remover restricción única de identificador_fiscal: {e}")
            
    print("Migración de base de datos finalizada.")

def clean_str(val):
    if val is None:
        return ""
    if isinstance(val, str):
        return val.replace('\x00', '').strip()
    return str(val).replace('\x00', '').strip()


def _as_date(val):
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    text = clean_str(val)
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt != "%Y%m%d" else text[:8], fmt).date()
        except ValueError:
            continue
    return None


def record_to_client_dict(record: dict) -> dict:
    """Normaliza un registro CLIGESCO / GesActi al dict de Support."""
    if not isinstance(record, dict):
        record = dict(record)
    ccod = clean_str(record.get("codigo") or record.get("CCOD") or record.get("CCod"))
    if ccod.isdigit() and len(ccod) <= 4:
        ccod = ccod.zfill(4)
    cdes = clean_str(record.get("nombre_fantasia") or record.get("CDES") or record.get("CDes") or record.get("CNOMFA"))
    craso = clean_str(record.get("razon_social") or record.get("CRASO") or record.get("CRaso"))
    cparte = clean_str(record.get("cparte") or record.get("CPARTE") or record.get("CParte"))
    cacti_raw = record.get("activo", record.get("CACTI", record.get("CActi", True)))
    if cacti_raw in (None, ""):
        cacti = True
    elif isinstance(cacti_raw, str):
        cacti = cacti_raw.strip().lower() not in ("0", "false", "f", "n", "no")
    else:
        cacti = bool(cacti_raw)
    if record.get("deleted") in (True, "true", "1", 1):
        cacti = False
    razon = craso or cdes or (f"Cliente {ccod}" if ccod else "Cliente")
    return {
        "codigo": ccod.upper() if ccod else "",
        "razon_social": razon,
        "nombre_fantasia": cdes or None,
        "identificador_fiscal": cparte or None,
        "cparte": cparte or None,
        "version_apollo": clean_str(record.get("version_apollo") or record.get("CVERSION") or record.get("CVersion")) or None,
        "activo": cacti,
        "saldo": float(record.get("saldo", record.get("CSALDO", record.get("CSaldo", 0.0))) or 0.0),
        "email": clean_str(record.get("email") or record.get("CEMAIL") or record.get("CEMail")) or None,
        "localidad": clean_str(record.get("localidad") or record.get("CLOCALIDA") or record.get("CLocalida")) or None,
        "fecha_ultimo_pago": _as_date(record.get("fecha_ultimo_pago") or record.get("CULPA") or record.get("CUlPa")),
        "fecha_registro": _as_date(record.get("fecha_registro") or record.get("CFECHA") or record.get("CFecha")),
        "vendedor_codigo": clean_str(record.get("vendedor_codigo") or record.get("CVENDEDOR") or record.get("CVendedor")) or None,
        "vendedor_nombre": clean_str(record.get("vendedor_nombre") or record.get("CNOMVEN") or record.get("CNomVen")) or None,
        "clasificacion_codigo": clean_str(record.get("clasificacion_codigo") or record.get("CCLAS") or record.get("CClas")) or None,
        "clasificacion_nombre": clean_str(record.get("clasificacion_nombre") or record.get("CNOMCLAS") or record.get("CNomClas")) or None,
        "extracto": clean_str(record.get("extracto") or record.get("CEXTRACTO")) or None,
        "cclifac": clean_str(record.get("cclifac") or record.get("CCLIFAC") or record.get("CCliFac")) or None,
    }


def apply_client_row(db, row: dict, *, partial: bool = False) -> str:
    """Inserta o actualiza un cliente. Devuelve 'inserted' | 'updated' | 'skipped'."""
    data = record_to_client_dict(row)
    codigo = data.get("codigo") or ""
    if not codigo:
        return "skipped"
    db_client = db.query(models.Client).filter(models.Client.codigo == codigo).first()
    if not db_client and data.get("cclifac"):
        fac = data["cclifac"]
        db_client = db.query(models.Client).filter(models.Client.cclifac == fac).first()
    if db_client:
        for key, value in data.items():
            if key == "codigo":
                continue
            if partial and value in (None, ""):
                continue
            setattr(db_client, key, value)
        return "updated"
    db.add(models.Client(**data))
    return "inserted"


def apply_clients_batch(db, rows: list) -> dict:
    inserted = updated = skipped = 0
    seen = set()
    for row in rows or []:
        data = record_to_client_dict(row if isinstance(row, dict) else dict(row))
        codigo = data.get("codigo") or ""
        if not codigo or codigo in seen:
            skipped += 1
            continue
        seen.add(codigo)
        action = apply_client_row(db, data, partial=False)
        if action == "inserted":
            inserted += 1
        elif action == "updated":
            updated += 1
        else:
            skipped += 1
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "total": inserted + updated}


def sync_data(dbf_path: str | None = None, db=None):
    """
    Lee CLIGESCO.DBF y sincroniza la información con PostgreSQL.
    Si no hay path usable (p.ej. producción sin M:), no toca la base.
    """
    if not dbf_path:
        try:
            from cligesco_dbf import primary_cligesco_path
            dbf_path = primary_cligesco_path() or r"\\192.168.10.24\X\programa\CLIGESCO.DBF"
        except Exception:
            dbf_path = r"\\192.168.10.24\X\programa\CLIGESCO.DBF"
    if not dbf_path or not os.path.exists(dbf_path):
        msg = f"No se encontró CLIGESCO.DBF en la ruta: {dbf_path}"
        print("Error:", msg)
        raise FileNotFoundError(msg)

    print("Leyendo CLIGESCO.DBF...", dbf_path)
    table = DBF(dbf_path, encoding="latin1", ignore_missing_memofile=True)
    own_db = db is None
    if own_db:
        db = SessionLocal()
    try:
        stats = apply_clients_batch(db, [dict(record) for record in table])
        db.commit()
        print(
            f"Sincronización completada: {stats['inserted']} insertados, "
            f"{stats['updated']} actualizados."
        )
        stats["path"] = dbf_path
        return stats
    except Exception:
        db.rollback()
        raise
    finally:
        if own_db:
            db.close()

if __name__ == "__main__":
    add_columns_safely()
    sync_data()
