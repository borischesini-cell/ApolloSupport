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
    def parse_erp_date(cls, raw):
        """Normaliza CULPA / fechas Harbour o DBF a datetime.date o None."""
        from datetime import datetime, date
        if raw in (None, "", "  /  /    ", "0000-00-00"):
            return None
        if isinstance(raw, date) and not isinstance(raw, datetime):
            return raw
        if isinstance(raw, datetime):
            return raw.date()
        text = str(raw).strip()
        if "T" in text:
            text = text.split("T", 1)[0]
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        return None

    @classmethod
    def get_client_account(cls, client_code: str) -> dict:
        """Saldo (CSaldo) y fecha de último pago (CULPA) desde Ventas\\Clientes del ERP."""
        code = str(client_code or "").strip()
        if not code:
            return {"saldo": 0.0, "fecha_ultimo_pago": None}

        codes = [code]
        if code.isdigit():
            for n in (7, 5, 4):
                padded = code.zfill(n)
                if padded not in codes:
                    codes.append(padded)
            stripped = code.lstrip("0") or "0"
            if stripped not in codes:
                codes.append(stripped)

        for c in codes:
            args = {
                "action": "browse",
                "folder": "ventas",
                "table": "clientes",
                "orden": "Nil",
                "filter": f'CCod=="{c}"',
                "fields": '["CCod","CSaldo","CULPA"]',
                "user": "--",
            }
            records = cls.execute(args) or []
            for rec in records:
                if not isinstance(rec, dict) or rec.get("error"):
                    continue
                saldo = float(rec.get("CSaldo", rec.get("CSALDO", 0.0)) or 0.0)
                fecha = cls.parse_erp_date(rec.get("CULPA") or rec.get("CUlPa") or rec.get("Culpa"))
                return {"saldo": saldo, "fecha_ultimo_pago": fecha, "ccod": str(rec.get("CCod") or c).strip()}

        return {"saldo": 0.0, "fecha_ultimo_pago": None}

    @classmethod
    def browse_clientes_saldos(cls) -> dict:
        """
        Mapa CCod -> {saldo, fecha_ultimo_pago} desde Ventas\\Clientes (CSaldo / CULPA).
        Una sola lectura del ERP para refrescar saldos en Support.
        """
        rows = cls.execute({
            "action": "browse",
            "folder": "ventas",
            "table": "clientes",
            "fields": '["CCod","CSaldo","CULPA"]',
            "user": "--",
        }) or []
        out = {}
        for rec in rows:
            if not isinstance(rec, dict) or rec.get("error"):
                continue
            ccod = str(rec.get("CCod") or rec.get("CCOD") or "").strip()
            if not ccod:
                continue
            saldo = float(rec.get("CSaldo", rec.get("CSALDO", 0.0)) or 0.0)
            fecha = cls.parse_erp_date(rec.get("CULPA") or rec.get("CUlPa") or rec.get("Culpa"))
            entry = {"saldo": saldo, "fecha_ultimo_pago": fecha}
            out[ccod] = entry
            # alias sin ceros a la izquierda
            if ccod.isdigit():
                out[ccod.lstrip("0") or "0"] = entry
                out[ccod.zfill(7)] = entry
        return out

    @classmethod
    def get_client_balance(cls, client_code: str) -> float:
        """
        Consulta el saldo real actual del cliente en el ERP de gestión.
        """
        return cls.get_client_account(client_code)["saldo"]

    @classmethod
    def get_estados_cuenta_corriente(cls) -> list:
        """
        Catálogo Ventas\\ClasiCli (Estados de Ctas Ctes del ERP).
        Campos: CCod / CDesc (DaClasi en GesActi).
        """
        rows = cls.execute({
            "action": "browse",
            "folder": "ventas",
            "table": "clasicli",
            "fields": '["CCod","CDesc"]',
            "user": "--",
        }) or []
        out = []
        for r in rows:
            if not isinstance(r, dict) or r.get("error"):
                continue
            codigo = str(r.get("CCod") or r.get("CCOD") or "").strip()
            if not codigo:
                continue
            desc = str(r.get("CDesc") or r.get("CDESC") or r.get("CDes") or "").strip()
            out.append({"codigo": codigo, "descripcion": desc})
        out.sort(key=lambda x: x["codigo"])
        return out

    @classmethod
    def get_client_lic_facturadas(cls, client_code: str, iva_pct: float = 21.0) -> list:
        """
        Artículos facturados al cliente (Ventas\\LisArtC + Stock\\Articulo),
        mismo listado que GesActi → Lic Facturadas / ListArt.
        """
        code = str(client_code or "").strip()
        if not code:
            return []

        codes = [code]
        if code.isdigit() and len(code) < 7:
            codes.append(code.zfill(7))

        rows = []
        for c in codes:
            args = {
                "action": "browse",
                "folder": "ventas",
                "table": "lisartc",
                "filter": f'LCli=="{c}"',
                "fields": '["LCli","LArt","LPre","LCan","LParte","LCC"]',
                "user": "--",
            }
            rows = cls.execute(args) or []
            if rows:
                break

        art_map = {}
        try:
            arts = cls.execute({
                "action": "browse",
                "folder": "stock",
                "table": "articulo",
                "fields": '["ACod","ADes"]',
                "user": "--",
            }) or []
            for a in arts:
                if isinstance(a, dict) and a.get("error"):
                    continue
                acod = str(a.get("ACod") or "").strip()
                if acod:
                    art_map[acod] = str(a.get("ADes") or "").strip()
        except Exception:
            art_map = {}

        iva = float(iva_pct or 0.0)
        out = []
        for r in rows:
            if not isinstance(r, dict) or r.get("error"):
                continue
            art = str(r.get("LArt") or "").strip()
            if len(art) != 7:
                continue
            pre = float(r.get("LPre") or 0.0)
            neto = pre / ((100.0 + iva) / 100.0) if iva > 0 else pre
            out.append({
                "l_cli": str(r.get("LCli") or "").strip(),
                "l_art": art,
                "a_des": art_map.get(art, ""),
                "precio_neto": round(neto, 5),
                "precio_final": round(pre, 5),
                "l_can": float(r.get("LCan") or 0.0),
                "l_parte": str(r.get("LParte") or "").strip(),
                "l_cc": str(r.get("LCC") or "").strip(),
            })
        return out

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
