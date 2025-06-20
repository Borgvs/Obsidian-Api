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


def to_relative_path(raw_path: str) -> str:
    """Converte o caminho WebDAV completo em um caminho relativo ao cofre."""
    path = unquote(raw_path)

    # Caminho base com e sem o domínio
    base_with_domain = WEBDAV_BASE_URL
    base_without_domain = WEBDAV_BASE_URL.replace("https://cloud.barch.com.br", "")

    if path.startswith(base_with_domain):
        path = path[len(base_with_domain):]
    elif path.startswith(base_without_domain):
        path = path[len(base_without_domain):]

    return path.strip("/")

# === LISTAR NOTAS ===
@app.route("/notes")
def list_notes():
    from urllib.parse import unquote
    import os

    query = request.args.get("q", "").lower()
    folder_filter = request.args.get("folder", "")
    limit = int(request.args.get("limit", "100"))

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

        rel_path = to_relative_path(elem.text)
        
        if folder_filter and not rel_path.startswith(folder_filter):
            continue
        if query and query not in rel_path.lower():
            continue

        notas.append({
            "name": os.path.basename(rel_path),
            "path": rel_path,
            "folder": os.path.dirname(rel_path)
        })

        if len(notas) >= limit:
            break

    return jsonify({"files": notas})

# === RETORNAR CONTEÚDO DE UMA NOTA ===
@app.route("/note/<path:filename>")
def get_note(filename):
    # Proteção contra input incorreto vindo com o WebDAV completo
    if "remote.php/dav/files/" in filename:
        filename = to_relative_path(filename)

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

        rel_path = to_relative_path(elem.text)
        folder = os.path.dirname(rel_path)
        folders.add(folder)

    return jsonify({"folders": sorted(list(folders))})


# === BUSCAR POR CONTEÚDO ===
@app.route("/search")
def search_notes():
    term = request.args.get("term", "").lower()
    if not term:
        return jsonify({"matches": []})

    headers = {"Depth": "infinity"}
    res = requests.request("PROPFIND", WEBDAV_BASE_URL, headers=headers, auth=AUTH)

    if res.status_code != 207:
        return jsonify({"error": f"Erro WebDAV: {res.status_code}"}), 500

    tree = ElementTree.fromstring(res.content)
    matches = []
    count = 0
    max_results = 30  # Evita travamento com muitos arquivos

    for elem in tree.findall(".//{DAV:}href"):
        path = unquote(elem.text)
        if not path.endswith(".md") or "Attachments" in path or "Readwise" in path:
            continue

        rel_path = to_relative_path(elem.text)
        file_url = WEBDAV_BASE_URL + quote(rel_path)
        try:
            file_res = requests.get(file_url, auth=AUTH)
            if file_res.status_code == 200 and term in file_res.text.lower():
                matches.append({
                    "name": os.path.basename(rel_path),
                    "path": rel_path,
                    "folder": os.path.dirname(rel_path)
                })
                count += 1
                if count >= max_results:
                    break
        except Exception:
            continue

    return jsonify({"matches": matches})

# === CRIAR NOTA ===
@app.route("/note", methods=["POST"])
def create_or_update_note():
    data = request.get_json()
    filename = data.get("filename")
    content = data.get("content", "")

    if not filename:
        return jsonify({"error": "O campo 'filename' é obrigatório"}), 400

    # Corrigir se o filename vier com prefixo WebDAV completo
    if "remote.php/dav/files" in filename:
        filename = to_relative_path(filename)

    file_url = WEBDAV_BASE_URL + quote(filename)
    res = requests.put(file_url, data=content.encode("utf-8"), auth=AUTH)

    if res.status_code in [200, 201, 204]:
        return jsonify({"message": "Nota salva com sucesso"})
    else:
        return jsonify({"error": f"Erro ao salvar nota: {res.status_code}"}), 500

# === INICIAR APLICATIVO ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
