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

def sync_data():
    """
    Lee CLIGESCO.DBF y sincroniza la información con PostgreSQL.
    """
    dbf_path = r"p:\ApolloSupport\bases\CLIGESCO.DBF"
    if not os.path.exists(dbf_path):
        print("Error: No se encontró CLIGESCO.DBF en la ruta:", dbf_path)
        return

    print("Leyendo CLIGESCO.DBF...")
    table = DBF(dbf_path, encoding='latin1')
    
    db = SessionLocal()
    try:
        print("Sincronizando clientes...")
        count_inserted = 0
        count_updated = 0
        count_deleted = 0
        
        # Guardaremos los códigos procesados para evitar duplicados en la misma transacción si la hubiera en la tabla DBF
        procesados = set()
        
        for record in table:
            # Extraer campos y limpiar espacios y bytes nulos
            ccod = clean_str(record.get("CCOD"))
            if not ccod:
                continue
                
            if ccod in procesados:
                print(f"Aviso: Código de cliente {ccod} duplicado en CLIGESCO.DBF. Saltando duplicado.")
                continue
                
            procesados.add(ccod)
            
            cacti = bool(record.get("CACTI", True))
            if not cacti:
                # Si el cliente no está activo, se borra directamente de la base de datos si existe
                db_client = db.query(models.Client).filter(models.Client.codigo == ccod).first()
                if db_client:
                    # Borrar primero tickets y dispositivos relacionados para evitar errores de clave foránea
                    for ticket in db_client.tickets:
                        db.delete(ticket)
                    for dev in db_client.devices:
                        db.delete(dev)
                    db.delete(db_client)
                    count_deleted += 1
                continue
            
            cdes = clean_str(record.get("CDES"))
            craso = clean_str(record.get("CRASO"))
            cparte = clean_str(record.get("CPARTE"))
            cversion = clean_str(record.get("CVERSION"))
            csaldo = float(record.get("CSALDO", 0.0) or 0.0)
            cemail = clean_str(record.get("CEMAIL"))
            clocalida = clean_str(record.get("CLOCALIDA"))
            cclifac = clean_str(record.get("CCLIFAC"))
            
            # Fechas (pueden venir como None o datetime.date)
            fecha_pago = record.get("CULPA")
            if isinstance(fecha_pago, datetime):
                fecha_pago = fecha_pago.date()
            elif not isinstance(fecha_pago, date):
                fecha_pago = None
                
            fecha_reg = record.get("CFECHA")
            if isinstance(fecha_reg, datetime):
                fecha_reg = fecha_reg.date()
            elif not isinstance(fecha_reg, date):
                fecha_reg = None
                
            vendedor_cod = clean_str(record.get("CVENDEDOR"))
            vendedor_nom = clean_str(record.get("CNOMVEN"))
            clas_cod = clean_str(record.get("CCLAS"))
            clas_nom = clean_str(record.get("CNOMCLAS"))
            extracto = record.get("CEXTRACTO")
            if extracto:
                extracto = extracto.replace('\x00', '').strip()
            else:
                extracto = None

            # Razón social default
            razon_social = craso if craso else cdes
            if not razon_social:
                razon_social = f"Cliente {ccod}"

            # Seteamos identificador_fiscal directamente
            identificador_fiscal = cparte if cparte else None

            # Buscar por código ERP
            db_client = db.query(models.Client).filter(models.Client.codigo == ccod).first()
            
            if db_client:
                # Actualizar campos existentes
                db_client.razon_social = razon_social
                db_client.nombre_fantasia = cdes
                db_client.identificador_fiscal = identificador_fiscal
                db_client.cparte = cparte
                db_client.version_apollo = cversion
                db_client.activo = cacti
                db_client.saldo = csaldo
                db_client.email = cemail
                db_client.localidad = clocalida
                db_client.fecha_ultimo_pago = fecha_pago
                db_client.fecha_registro = fecha_reg
                db_client.vendedor_codigo = vendedor_cod
                db_client.vendedor_nombre = vendedor_nom
                db_client.clasificacion_codigo = clas_cod
                db_client.clasificacion_nombre = clas_nom
                db_client.extracto = extracto
                db_client.cclifac = cclifac
                count_updated += 1
            else:
                # Crear nuevo cliente
                db_client = models.Client(
                    codigo=ccod,
                    razon_social=razon_social,
                    nombre_fantasia=cdes,
                    identificador_fiscal=identificador_fiscal,
                    cparte=cparte,
                    version_apollo=cversion,
                    activo=cacti,
                    saldo=csaldo,
                    email=cemail,
                    localidad=clocalida,
                    fecha_ultimo_pago=fecha_pago,
                    fecha_registro=fecha_reg,
                    vendedor_codigo=vendedor_cod,
                    vendedor_nombre=vendedor_nom,
                    clasificacion_codigo=clas_cod,
                    clasificacion_nombre=clas_nom,
                    extracto=extracto,
                    cclifac=cclifac
                )
                db.add(db_client)
                count_inserted += 1
                
        db.commit()
        print(f"Sincronización completada: {count_inserted} insertados, {count_updated} actualizados, {count_deleted} inactivos eliminados.")
    except Exception as e:
        db.rollback()
        print("Error durante la sincronización:", e)
    finally:
        db.close()

if __name__ == "__main__":
    add_columns_safely()
    sync_data()
