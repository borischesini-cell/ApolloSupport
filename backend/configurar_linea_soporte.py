#!/usr/bin/env python3
"""
Script interactivo para configurar la línea WhatsApp de soporte (Grupo Master SRL).

Uso:
    python configurar_linea_soporte.py

Requisitos:
    - Backend corriendo en http://127.0.0.1:8001
    - Token de admin válido
    - IDs de Meta (waba_id, phone_number_id, access_token, pin)
"""

import requests
import json
import sys
from getpass import getpass

BASE_URL = "http://127.0.0.1:8001"

def print_step(n, title):
    print(f"\n{'='*70}")
    print(f"PASO {n}: {title}")
    print('='*70)

def print_json(data):
    print(json.dumps(data, indent=2, ensure_ascii=False))

def get_input(prompt, required=True, default=None):
    """Obtener input del usuario con validación."""
    while True:
        value = input(prompt).strip()
        if not value and required:
            print("  ⚠ Este campo es obligatorio")
            continue
        if not value and default:
            return default
        return value

def check_backend():
    """Verificar que el backend esté corriendo."""
    print_step(0, "Verificar backend")
    try:
        r = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if r.status_code == 200:
            print("✓ Backend corriendo en", BASE_URL)
            return True
    except:
        pass
    print(f"✗ No se pudo conectar al backend en {BASE_URL}")
    print("  Verificar que ApolloBackend esté corriendo:")
    print("  nssm status ApolloBackend")
    return False

def get_admin_token():
    """Obtener token de admin."""
    print("\nToken de admin (Bearer):")
    print("  Se obtiene con: POST /api/auth/login")
    print("  O del .env del servidor si hay uno hardcodeado para pruebas")
    return get_input("Token: ")

def get_meta_ids():
    """Obtener IDs de Meta."""
    print_step(1, "Obtener IDs de Meta")
    print("\nNecesitás estos valores del panel de Meta for Developers:")
    print("  1. waba_id: WhatsApp → API Setup → Business Account ID")
    print("  2. phone_number_id: En la URL del número en WhatsApp → Phone numbers")
    print("  3. access_token: System Users → Generar token con permisos WhatsApp")
    print("  4. pin: WhatsApp → API Setup → Generate PIN (6 dígitos)")
    print()

    waba_id = get_input("WABA ID (Business Account ID): ")
    phone_number_id = get_input("Phone Number ID: ")
    print("\nAccess Token (se cifra al guardar, no se muestra después):")
    access_token = getpass("  Token: ")
    pin = get_input("PIN de 6 dígitos: ")

    return waba_id, phone_number_id, access_token, pin

def get_client_info():
    """Obtener información del cliente."""
    print_step(2, "Información del cliente")
    print("\nPara 'nosotros' (soporte interno), usamos el cliente Grupo Master SRL.")
    print("Si no existe en la tabla clients, hay que crearlo primero.")
    print()

    client_id = get_input("Client ID de Grupo Master SRL (o cliente de soporte): ", default="")
    if not client_id:
        print("\n⚠ Necesitás el client_id. Podés buscarlo con:")
        print(f"  curl -H 'Authorization: Bearer <TOKEN>' {BASE_URL}/api/clients")
        client_id = get_input("Client ID: ")

    business_id = get_input("Business ID (Meta App ID, ej: 807028593951690): ", default="807028593951690")
    display_phone = get_input("Display phone number (ej: +5493446527365): ", default="+5493446527365")
    verified_name = get_input("Verified name (ej: GRUPO MASTER SRL): ", default="GRUPO MASTER SRL")

    return int(client_id), business_id, display_phone, verified_name

def create_account(token, client_id, business_id, waba_id, phone_number_id,
                   access_token, pin, display_phone, verified_name):
    """Paso 1: Crear la cuenta."""
    print_step(3, "Dar de alta la cuenta en ApolloSupport")

    payload = {
        "client_id": client_id,
        "business_id": business_id,
        "waba_id": waba_id,
        "phone_number_id": phone_number_id,
        "display_phone_number": display_phone,
        "verified_name": verified_name,
        "access_token": access_token,
        "pin": pin,
        "allowed_categories": "UTILITY,SERVICE",
        "monthly_message_quota": 10000,
        "rate_currency": "USD",
        "notes": "Linea de soporte interno - reemplazo de neonize",
        "erp_send_enabled": False,
        "erp_invoice_template": "factura_apollo",
        "erp_invoice_language": "es"
    }

    print("\nPOST /api/whatsapp/accounts")
    print("Payload:")
    print_json({k: v for k, v in payload.items() if k != "access_token"})
    print("  access_token: <CIFRADO>")

    try:
        r = requests.post(
            f"{BASE_URL}/api/whatsapp/accounts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json=payload,
            timeout=30
        )

        if r.status_code == 200:
            data = r.json()
            print("\n✓ Cuenta creada exitosamente")
            print(f"  Account ID: {data['id']}")
            print(f"  Status: {data['status']}")
            return data['id']
        else:
            print(f"\n✗ Error {r.status_code}:")
            print_json(r.json())
            return None
    except Exception as e:
        print(f"\n✗ Excepción: {e}")
        return None

def register_number(token, account_id):
    """Paso 2: Registrar el número en Meta."""
    print_step(4, "Registrar el número en Meta")

    print(f"\nPOST /api/whatsapp/accounts/{account_id}/register")
    print("  Esto registra el número con el PIN de 6 dígitos.")
    print("  ⚠ El número deja de poder usarse en la app de WhatsApp común.")

    confirm = input("\n¿Continuar? (s/N): ").strip().lower()
    if confirm != 's':
        print("  Cancelado")
        return False

    try:
        r = requests.post(
            f"{BASE_URL}/api/whatsapp/accounts/{account_id}/register",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )

        if r.status_code == 200:
            data = r.json()
            print("\n✓ Número registrado")
            print(f"  Status: {data['status']}")
            return True
        else:
            print(f"\n✗ Error {r.status_code}:")
            print_json(r.json())
            return False
    except Exception as e:
        print(f"\n✗ Excepción: {e}")
        return False

def test_account(token, account_id):
    """Paso 3: Probar la conexión con Meta."""
    print_step(5, "Probar la conexión con Meta")

    print(f"\nPOST /api/whatsapp/accounts/{account_id}/test")
    print("  Pregunta a Meta por el número: token, registro y límites.")

    try:
        r = requests.post(
            f"{BASE_URL}/api/whatsapp/accounts/{account_id}/test",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )

        if r.status_code == 200:
            data = r.json()
            print("\n✓ Conexión exitosa")
            print(f"  Status: {data['status']}")
            print(f"  Quality rating: {data['cuenta'].get('quality_rating', 'N/A')}")
            print(f"  Messaging limit: {data['cuenta'].get('messaging_limit_tier', 'N/A')}")
            print(f"  Verified name: {data['cuenta'].get('verified_name', 'N/A')}")
            return True
        else:
            print(f"\n✗ Error {r.status_code}:")
            print_json(r.json())
            return False
    except Exception as e:
        print(f"\n✗ Excepción: {e}")
        return False

def enable_erp(token, account_id):
    """Paso 4: Habilitar el canal ERP."""
    print_step(6, "Habilitar el canal ERP")

    print(f"\nPUT /api/whatsapp/accounts/{account_id}")
    print("  Habilita erp_send_enabled para que el puesto pueda enviar facturas.")

    try:
        r = requests.put(
            f"{BASE_URL}/api/whatsapp/accounts/{account_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            },
            json={"erp_send_enabled": True},
            timeout=30
        )

        if r.status_code == 200:
            data = r.json()
            print("\n✓ Canal ERP habilitado")
            print(f"  erp_send_enabled: {data['erp_send_enabled']}")
            print(f"  erp_invoice_template: {data.get('erp_invoice_template', 'N/A')}")
            return True
        else:
            print(f"\n✗ Error {r.status_code}:")
            print_json(r.json())
            return False
    except Exception as e:
        print(f"\n✗ Excepción: {e}")
        return False

def rotate_key(token, client_code):
    """Paso 5: Generar api_key para el canal ERP."""
    print_step(7, "Generar api_key para el canal ERP")

    print(f"\nPOST /api/whatsapp/erp/clients/{client_code}/rotate-key")
    print("  ⚠ La api_key se muestra UNA SOLA VEZ. Guárdala en un lugar seguro.")

    confirm = input("\n¿Continuar? (s/N): ").strip().lower()
    if confirm != 's':
        print("  Cancelado")
        return None

    try:
        r = requests.post(
            f"{BASE_URL}/api/whatsapp/erp/clients/{client_code}/rotate-key",
            headers={"Authorization": f"Bearer {token}"},
            timeout=30
        )

        if r.status_code == 200:
            data = r.json()
            print("\n✓ api_key generada")
            print(f"  Client code: {data['client_code']}")
            print(f"  API Key: {data['api_key']}")
            print(f"\n  ⚠ GUARDAR ESTA CLAVE: {data['api_key']}")
            print(f"  Se guarda en Client.apikey_apollo y no se muestra después.")
            return data['api_key']
        else:
            print(f"\n✗ Error {r.status_code}:")
            print_json(r.json())
            return None
    except Exception as e:
        print(f"\n✗ Excepción: {e}")
        return None

def print_ini_config(account_id, client_code, api_key, gesacti_key):
    """Mostrar la configuración del INI."""
    print_step(8, "Configuración del INI del puesto")

    print("\nAgregar esta sección a ..\\GescomPdf.ini en el puesto:")
    print()
    print("[WhatsApp]")
    print(f"CloudUrl={BASE_URL}")
    print(f"CloudCode={client_code}")
    print(f"CloudGesActi={gesacti_key}")
    print("CloudSerial=<SERIAL_GESCOM_DEL_PUESTO>")
    print("CloudUser=<USUARIO_GESCOM>")
    print("CloudPathPfx=C:\\ApolloSupport\\wa_logs")
    print("CloudTemplate=factura_apollo")
    print("CloudLanguage=es")
    print("CloudLog=1")

    print("\nReemplazar:")
    print("  <SERIAL_GESCOM_DEL_PUESTO>: Serial de GesCom (menú Acerca de)")
    print("  <USUARIO_GESCOM>: Usuario con el que se loguea el operador")

def main():
    print("="*70)
    print("CONFIGURACIÓN DE LÍNEA WHATSAPP PARA SOPORTE")
    print("Grupo Master SRL - 3446-675303")
    print("="*70)

    # Paso 0: Verificar backend
    if not check_backend():
        sys.exit(1)

    # Paso 1: Token de admin
    token = get_admin_token()
    if not token:
        print("✗ Token requerido")
        sys.exit(1)

    # Paso 2: IDs de Meta
    waba_id, phone_number_id, access_token, pin = get_meta_ids()

    # Paso 3: Información del cliente
    client_id, business_id, display_phone, verified_name = get_client_info()

    # Paso 4: Crear cuenta
    account_id = create_account(
        token, client_id, business_id, waba_id, phone_number_id,
        access_token, pin, display_phone, verified_name
    )
    if not account_id:
        print("\n✗ No se pudo crear la cuenta")
        sys.exit(1)

    # Paso 5: Registrar número
    if not register_number(token, account_id):
        print("\n✗ No se pudo registrar el número")
        print("  Podés intentar de nuevo con:")
        print(f"  curl -X POST {BASE_URL}/api/whatsapp/accounts/{account_id}/register \\")
        print(f"    -H 'Authorization: Bearer {token}'")
        sys.exit(1)

    # Paso 6: Probar conexión
    if not test_account(token, account_id):
        print("\n✗ No se pudo probar la conexión")
        print("  Podés intentar de nuevo con:")
        print(f"  curl -X POST {BASE_URL}/api/whatsapp/accounts/{account_id}/test \\")
        print(f"    -H 'Authorization: Bearer {token}'")
        sys.exit(1)

    # Paso 7: Habilitar canal ERP
    if not enable_erp(token, account_id):
        print("\n✗ No se pudo habilitar el canal ERP")
        sys.exit(1)

    # Paso 8: Generar api_key
    client_code = get_input("\nCódigo del cliente (ej: GM001): ")
    api_key = rotate_key(token, client_code)
    if not api_key:
        print("\n✗ No se pudo generar la api_key")
        sys.exit(1)

    # Paso 9: Mostrar configuración del INI
    gesacti_key = get_input("\nGESACTI_SYNC_KEY del servidor (del .env): ")
    print_ini_config(account_id, client_code, api_key, gesacti_key)

    # Resumen final
    print_step(9, "Configuración completada")
    print("\n✓ Línea configurada exitosamente")
    print(f"  Account ID: {account_id}")
    print(f"  Client ID: {client_id}")
    print(f"  Phone: {display_phone}")
    print(f"  Status: connected")
    print(f"  ERP enabled: true")
    print(f"\nPróximos pasos:")
    print("  1. Configurar el INI en el puesto (ver arriba)")
    print("  2. Probar el envío de una factura desde GesCom")
    print("  3. Verificar los logs en el servidor y el puesto")
    print(f"\nVer consumo:")
    print(f"  curl -H 'Authorization: Bearer {token}' \\")
    print(f"    '{BASE_URL}/api/whatsapp/erp/clients/{client_code}/usage?month=2026-09'")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠ Interrumpido por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error inesperado: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
