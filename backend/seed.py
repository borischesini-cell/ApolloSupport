"""
-------------------------------------------------------------------------
Script Semilla (Seeder)
Proyecto: ApolloSupport
Descripción: Inserta algunos datos falsos en PostgreSQL (Clientes y Tickets)
para que el Dashboard de React tenga información estructurada y real que mostrar.
-------------------------------------------------------------------------
"""
from database import SessionLocal
from models import Client, Ticket, User

def seed_database():
    db = SessionLocal()
    
    # 1. Crear un Cliente Ficticio
    cliente_existe = db.query(Client).filter(Client.razon_social == "Supermercados El Sol").first()
    if not cliente_existe:
        nuevo_cliente = Client(
            razon_social="Supermercados El Sol",
            identificador_fiscal="30-12345678-9",
            version_apollo="v5.4.0",
            telefono="011-5555-4444"
        )
        db.add(nuevo_cliente)
        db.commit()
        db.refresh(nuevo_cliente)
        print("Cliente 'Supermercados El Sol' creado.")
    else:
        nuevo_cliente = cliente_existe
        
    # 2. Insertar Tickets de Ejemplo
    ticket_existe = db.query(Ticket).filter(Ticket.client_id == nuevo_cliente.id).first()
    if not ticket_existe:
        ticket1 = Ticket(
            client_id=nuevo_cliente.id,
            asunto="Error de AFIP al emitir Factura Electrónica B",
            descripcion="El cajero 1 reporta que cada vez que intenta facturar, AFIP devuelve timeout.",
            estado="nuevo",
            prioridad="alta"
        )
        ticket2 = Ticket(
            client_id=nuevo_cliente.id,
            asunto="Capacitación módulo de contabilidad solicitada",
            descripcion="La nueva contadora necesita una explicación del módulo de asientos automáticos.",
            estado="en_curso",
            prioridad="media"
        )
        ticket3 = Ticket(
            client_id=nuevo_cliente.id,
            asunto="Punto de venta frizado tras actualización",
            descripcion="Después de instalar el último parche de Apollo, la terminal 3 quedó colgada en la pantalla de inicio.",
            estado="escalado_a_dev",
            prioridad="critica"
        )
        
        db.add_all([ticket1, ticket2, ticket3])
        db.commit()
        print("Tickets falsos sembrados en la base de datos.")
    else:
        print("La base de datos ya tenía tickets.")
        
    db.close()

if __name__ == "__main__":
    seed_database()
