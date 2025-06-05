from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote, unquote
from xml.etree import ElementTree
import os

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
    query = request.args.get("q", "").lower()
    folder_filter = request.args.get("folder", "")

    headers = {"Depth": "infinity"}
    res = requests.request("PROPFIND", WEBDAV_BASE_URL, headers=headers, auth=AUTH)

    if res.status_code != 207:
        return jsonify({"error": f"Erro WebDAV: {res.status_code}"}), 500

    tree = ElementTree.fromstring(res.content)
    notas = []

    for elem in tree.findall(".//{DAV:}href"):
        path = unquote(elem.text)
        if not path.endswith(".md"):
            continue
        if "Attachments" in path or "Readwise" in path:
            continue

        rel_path = path.replace(WEBDAV_BASE_URL.replace("https://cloud.barch.com.br", ""), "").strip("/")

        if folder_filter and not rel_path.startswith(folder_filter):
            continue
        if query and query not in rel_path.lower():
            continue

        notas.append({
            "name": os.path.basename(rel_path),
            "path": rel_path,
            "folder": os.path.dirname(rel_path)
        })

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


# === LISTAR PASTAS ÚNICAS ===
@app.route("/folders")
def list_folders():
    headers = {"Depth": "infinity"}
    res = requests.request("PROPFIND", WEBDAV_BASE_URL, headers=headers, auth=AUTH)

    if res.status_code != 207:
        return jsonify({"error": f"Erro WebDAV: {res.status_code}"}), 500

    tree = ElementTree.fromstring(res.content)
    folders = set()

    for elem in tree.findall(".//{DAV:}href"):
        path = unquote(elem.text)
        if not path.endswith(".md"):
            continue
        if "Attachments" in path or "Readwise" in path:
            continue

        rel_path = path.replace(WEBDAV_BASE_URL.replace("https://cloud.barch.com.br", ""), "").strip("/")
        folder = os.path.dirname(rel_path)
        folders.add(folder)

    return jsonify({"folders": sorted(list(folders))})


# === BUSCAR POR CONTEÚDO ===
@app.route("/search")
def search_notes():
    term = request.args.get("term", "").lower()
    if not term:
        return jsonify({"error": "Termo de busca não fornecido"}), 400

    headers = {"Depth": "infinity"}
    res = requests.request("PROPFIND", WEBDAV_BASE_URL, headers=headers, auth=AUTH)

    if res.status_code != 207:
        return jsonify({"error": f"Erro WebDAV: {res.status_code}"}), 500

    tree = ElementTree.fromstring(res.content)
    matches = []

    for elem in tree.findall(".//{DAV:}href"):
        path = unquote(elem.text)
        if not path.endswith(".md"):
            continue
        if "Attachments" in path or "Readwise" in path:
            continue

        rel_path = path.replace(WEBDAV_BASE_URL.replace("https://cloud.barch.com.br", ""), "").strip("/")
        file_url = WEBDAV_BASE_URL + quote(rel_path)

        file_res = requests.get(file_url, auth=AUTH)
        if file_res.status_code == 200 and term in file_res.text.lower():
            matches.append({
                "name": os.path.basename(rel_path),
                "path": rel_path,
                "folder": os.path.dirname(rel_path)
            })

    return jsonify({"matches": matches})


# === CRIAR NOTA ===
@app.route("/note", methods=["POST"])
@require_token
def create_or_update_note():
    data = request.get_json()
    filename = data.get("filename")
    content = data.get("content", "")

    if not filename or not filename.endswith(".md"):
        return jsonify({"error": "Nome do arquivo inválido"}), 400

    full_url = WEBDAV_BASE_URL + quote(filename)
    headers = {"Content-Type": "text/markdown"}

    res = requests.put(full_url, data=content.encode("utf-8"), headers=headers, auth=AUTH)

    if res.status_code in [200, 201, 204]:
        return jsonify({"message": "Nota criada/atualizada com sucesso"})
    else:
        return jsonify({"error": f"Erro ao salvar nota: {res.status_code}"}), 500


# === INICIAR APLICATIVO ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
