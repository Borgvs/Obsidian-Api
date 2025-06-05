from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote
from xml.etree import ElementTree

app = Flask(__name__)
CORS(app)

# === CONFIGURAÇÕES ===
USERNAME = "gustavo"
PASSWORD = "Xkntc-ypdG5-3SL5H-NP2GX-4YC9W"
WEBDAV_BASE_URL = "https://cloud.barch.com.br/remote.php/dav/files/Gustavo/Barch%20Adm/03.Recursos/ObsidianVault/Gustavo/"
AUTH = HTTPBasicAuth(USERNAME, PASSWORD)

# === LISTAR NOTAS ===
@app.route("/notes")
def list_notes():
    headers = {"Depth": "1"}
    res = requests.request("PROPFIND", WEBDAV_BASE_URL, headers=headers, auth=AUTH)

    if res.status_code != 207:
        return jsonify({"error": f"Erro WebDAV: {res.status_code}"}), 500

    tree = ElementTree.fromstring(res.content)
    notas = []

    for elem in tree.findall(".//{DAV:}href"):
        nome = elem.text.split("/")[-1]
        if nome.endswith(".md"):
            notas.append(nome)

    return jsonify({"files": notas})


# === RETORNAR CONTEÚDO DE UMA NOTA ===
@app.route("/note/<path:filename>")
def get_note(filename):
    file_url = WEBDAV_BASE_URL + quote(filename)
    res = requests.get(file_url, auth=AUTH)

    if res.status_code == 200:
        return jsonify({"content": res.text})
    elif res.status_code == 404:
        return jsonify({"error": "Nota não encontrada"}), 404
    else:
        return jsonify({"error": f"Erro ao buscar nota: {res.status_code}"}), 500


# === INICIAR APLICATIVO ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
