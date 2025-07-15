# app.py
import os, io, json, datetime, base64
from flask import Flask, request, render_template_string
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

app = Flask(__name__)
ACTIVACIONES_FILE = "activaciones.json"

# --- Cargar clave privada desde variable de entorno segura ---
def cargar_clave_privada():
    key_data = os.environ.get("PRIVATE_KEY_PEM").encode()
    return serialization.load_pem_private_key(io.BytesIO(key_data).read(), password=None)

# --- Leer activaciones existentes ---
def cargar_activaciones():
    if os.path.exists(ACTIVACIONES_FILE):
        with open(ACTIVACIONES_FILE, "r") as f:
            return json.load(f)
    return {}

# --- Guardar nueva activación ---
def registrar_activacion(package_id, machine_id):
    data = cargar_activaciones()
    data[package_id] = {
        "machine_id": machine_id,
        "fecha": str(datetime.date.today())
    }
    with open(ACTIVACIONES_FILE, "w") as f:
        json.dump(data, f, indent=2)

# --- Generar y firmar licencia ---
def generar_licencia(package_id, machine_id, fecha_exp, plan):
    datos = f"pkg={package_id};mid={machine_id};exp={fecha_exp}"
    if plan:
        datos += f";plan={plan}"
    private_key = cargar_clave_privada()
    firma = private_key.sign(
        datos.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
        hashes.SHA256()
    )
    return f"{datos}|{base64.b64encode(firma).decode()}"

# --- Página automática desde el QR ---
@app.route("/activar")
def activar():
    pkg = request.args.get("package_id")
    mid = request.args.get("machine_id")

    if not pkg or not mid:
        return "Faltan parámetros en la URL", 400

    usadas = cargar_activaciones()
    if pkg in usadas:
        return f"<h2>❌ Este package_id ya fue activado.</h2><p>{pkg}</p>", 400

    fecha_default = (datetime.date.today() + datetime.timedelta(days=30)).strftime("%Y-%m-%d")
    plan_default = "pro"

    licencia = generar_licencia(pkg, mid, fecha_default, plan_default)
    registrar_activacion(pkg, mid)

    return render_template_string(f"""
        <h2>✅ Licencia generada automáticamente</h2>
        <p><b>Fecha expiración:</b> {fecha_default}</p>
        <p><b>Plan:</b> {plan_default}</p>
        <textarea id='licencia' rows='6' cols='80'>{licencia}</textarea>
        <br><br>
        <button onclick="descargarPDF()">📄 Descargar como PDF</button>
        <br><br>
        <small>Licencia válida solo para esta máquina y este paquete</small>

        <script>
            function descargarPDF() {
                const licencia = document.getElementById('licencia').value;
                const blob = new Blob([licencia], { type: 'application/pdf' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = 'licencia_snapq.pdf';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
            }
        </script>
    """)

# --- Página de inicio (opcional) ---
@app.route("/")
def index():
    return "<h2>Servidor de Activación SnapQ (Render)</h2><p>Escanea el QR desde SnapQ para recibir tu licencia.</p>"

# --- Lanzamiento ---
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
