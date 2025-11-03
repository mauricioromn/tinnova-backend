import os, time
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()
url = os.getenv("SUPABASE_URL")
key = os.getenv("SUPABASE_SERVICE_ROLE")
assert url and key, "Falta SUPABASE_URL o SUPABASE_SERVICE_ROLE"

supabase: Client = create_client(url, key)

# Inserta un registro de diagnóstico en tu tabla 'proformas' o 'cotizaciones'
# Usa la tabla que ya tengas creada. Aquí muestro 'proformas' como ejemplo.
payload = {
    "cliente": "DIAGNOSTICO",
    "fecha": time.strftime("%Y-%m-%d"),
    "total": 0,
    "creado_por": "diagnostico-script",
}
resp = supabase.table("proformas").insert(payload).execute()
print("Insert OK:", resp.data)

# Lee último registro
resp = supabase.table("proformas").select("*").order("id", desc=True).limit(1).execute()
print("Último:", resp.data)
