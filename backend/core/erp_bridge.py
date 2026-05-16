import os
import json
import requests
import time
from base64 import urlsafe_b64decode, b64decode

from dotenv import load_dotenv

load_dotenv()

class ERPBridge:
    # URL por defecto del proxy PHP remoto de Xailer para modo CONNECT (apunta a localhost para desarrollo)
    REMOTE_HOST = os.getenv("ERP_REMOTE_HOST", "http://localhost")
    
    @classmethod
    def serialize_xailer_json(cls, args: dict) -> str:
        """
        Serializa un diccionario en un formato JSON crudo tolerante esperado por el motor de Xailer/Harbour.
        Esto es crítico porque arreglos/listas o valores numéricos marcados con prefijos especiales
        no deben estar encerrados entre comillas en el JSON de salida.
        """
        json_string = "{\n"
        for key, value in args.items():
            json_string += f'"{key}": '
            if isinstance(value, str):
                if value.startswith("[") or value.startswith("{"):
                    json_string += value
                elif value.startswith("#"):
                    json_string += value[1:]
                else:
                    json_string += f'"{value}"'
            else:
                json_string += json.dumps(value)
            json_string += ",\n"
        
        # Eliminar la última coma redundante
        pos = json_string.rfind(",")
        if pos != -1:
            json_string = json_string[:pos] + json_string[pos+1:]
        json_string += "}\n"
        return json_string

    @classmethod
    def execute(cls, args: dict) -> list:
        """
        Ejecuta un comando en el ERP de manera remota (vía proxy PHP xailer.php).
        """
        url = f"{cls.REMOTE_HOST.rstrip('/')}/IA/xailer.php"
        payload_s = cls.serialize_xailer_json(args)
        headers = {
            "Authorization": "Bearer tu_token_secreto_aqui",
            "Content-Type": "application/json; charset=utf-8"
        }
        try:
            response = requests.post(url, data=payload_s.encode('utf-8'), headers=headers, timeout=15.0)
            results = []
            for line in response.text.split("\n"):
                line = line.strip()
                if line:
                    try:
                        parsed = json.loads(line)
                        if isinstance(parsed, list):
                            results.extend(parsed)
                        else:
                            results.append(parsed)
                    except Exception:
                        continue
            return results
        except Exception as e:
            raise RuntimeError(f"Error al consultar el ERP remoto en {url}: {e}")

    @classmethod
    def get_client_balance(cls, client_code: str) -> float:
        """
        Consulta el saldo real actual del cliente en el ERP de gestión.
        """
        args = {
            "action": "browse",
            "folder": "ventas",
            "table": "clientes",
            "orden": "Nil",
            "filter": f'CCod=="{client_code}"',
            "fields": '["CSaldo"]',
            "user": "--"
        }
        
        records = cls.execute(args)
        if records and len(records) > 0:
            return float(records[0].get("CSaldo", 0.0))
        return 0.0

    @classmethod
    def get_client_extracto(cls, client_code: str, desde_iso: str = None, hasta_iso: str = None) -> list:
        """
        Devuelve el listado de transacciones histórico (extracto/cuenta corriente) de un cliente específico.
        """
        # Calcular fechas por defecto si no son provistas (últimos 150 días)
        if not desde_iso or not hasta_iso:
            now = time.time()
            if not hasta_iso:
                hasta_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now))
            if not desde_iso:
                desde_iso = time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime(now - 150*24*60*60))
                
        args = {
            "action": "function",
            "name": "extractoCliente",
            "codigo": client_code,
            "desde": desde_iso,
            "hasta": hasta_iso,
            "fields": '["Fecha", "Documento", "Importe", "Saldo", "CodFac"]',
            "user": "--"
        }
        
        return cls.execute(args)

    @classmethod
    def get_voucher_pdf(cls, hash_fac: str) -> tuple:
        """
        Llama al motor de Harbour para renderizar el PDF oficial del ERP para un comprobante específico.
        Devuelve una tupla (nombre_archivo_sugerido, bytes_pdf_decodificados).
        """
        args = {
            "action": "function",
            "name": "generaPDF",
            "codigo": hash_fac,
            "user": "--"
        }
        
        records = cls.execute(args)
        if not records or len(records) == 0:
            raise FileNotFoundError("No se recibió respuesta del motor Harbour para generar el PDF.")
            
        record = records[0]
        hash_pdf = record.get("hashPdf")
        if not hash_pdf:
            raise ValueError(f"El comprobante {hash_fac} no posee flujo PDF válido de retorno o el código es inválido.")
            
        # Decodificar el stream en Base64 seguro
        try:
            pdf_bytes = urlsafe_b64decode(hash_pdf)
        except Exception:
            try:
                pdf_bytes = b64decode(hash_pdf)
            except Exception as e:
                raise ValueError(f"Error decodificando flujo Base64 del PDF: {e}")
                
        document_name = record.get("Documento", f"comprobante_{hash_fac}.pdf")
        return document_name, pdf_bytes
