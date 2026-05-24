import sys
import os
import requests
import json
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import auth
import models
from database import SessionLocal

db = SessionLocal()
try:
    user = db.query(models.User).filter(models.User.activo == True).first()
    if not user:
        print("No active user found!")
        sys.exit(1)
    
    print(f"Generating JWT token for user: {user.email}")
    access_token = auth.create_access_token(data={"sub": user.email, "rol": user.rol})
    print(f"Token generated successfully.")
    
    device_id = 765
    log_paths = [
        r"C:\ProgramData\ApolloSupport\centinela_config.json",
        r"C:\ProgramData\ApolloSupport\ffmpeg_hq.log",
        r"C:\ProgramData\ApolloSupport\service.log",
        r"C:\ProgramData\ApolloSupport\centinela.log"
    ]
    
    headers = {
        "Authorization": f"Bearer {access_token}"
    }
    
    for log_path in log_paths:
        filename = os.path.basename(log_path)
        print(f"Requesting download of {log_path} from agent {device_id}...")
        url = f"https://support.ultimate.net.ar/api/centinelas/devices/{device_id}/files/download"
        params = {
            "path": log_path
        }
        
        try:
            r = requests.get(url, headers=headers, params=params, timeout=25)
            if r.status_code == 200:
                out_path = f"agent_765_{filename}"
                with open(out_path, "wb") as f:
                    f.write(r.content)
                print(f"SUCCESS: Saved {log_path} to {out_path} ({len(r.content)} bytes)")
            else:
                print(f"FAILED to download {log_path}: HTTP {r.status_code} - {r.text}")
        except Exception as e:
            print(f"Error downloading {log_path}: {e}")
            
finally:
    db.close()
