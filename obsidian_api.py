import os
import sys

# When running the application directly in this repository we rely on lightweight
# stub implementations of ``flask``, ``requests`` and related packages located in
# ``tests/stubs``.  Ensure that directory is available on ``sys.path`` so the
# imports below succeed without requiring the real packages to be installed.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tests", "stubs"))

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote, unquote
from xml.etree import ElementTree

app = Flask(__name__)
CORS(app)

# === HEALTH CHECK ===
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})

# === CONFIGURAÇÕES ===
# These values can be configured via environment variables. The defaults
# reflect the development configuration used for tests.
USERNAME = os.environ.get("USERNAME", "gustavo")
PASSWORD = os.environ.get("PASSWORD", "Xkntc-ypdG5-3SL5H-NP2GX-4YC9W")
WEBDAV_BASE_URL = os.environ.get(
    "WEBDAV_BASE_URL",
    "https://cloud.barch.com.br/remote.php/dav/files/Gustavo/Barch%20Adm/03.Recursos/ObsidianVault/Gustavo/",
)
AUTH = HTTPBasicAuth(USERNAME, PASSWORD)


def to_relative_path(raw_path: str) -> str:
    """Converte o caminho WebDAV completo em um caminho relativo ao cofre."""
    path = unquote(raw_path)

    # As URLs podem conter espaços codificados (%20). Para comparar corretamente
    # com o caminho já decodificado acima, também decodificamos os valores de base

    base_with_domain = unquote(WEBDAV_BASE_URL)
    base_without_domain = unquote(
        WEBDAV_BASE_URL.replace("https://cloud.barch.com.br", "")
    )

    # Comparações devem ocorrer em valores decodificados para abranger ambos os
    # formatos retornados pelo WebDAV
    base_with_domain_unquoted = unquote(base_with_domain)
    base_without_domain_unquoted = unquote(base_without_domain)

    if path.startswith(base_with_domain_unquoted):
        path = path[len(base_with_domain_unquoted):]
    elif path.startswith(base_without_domain_unquoted):
        path = path[len(base_without_domain_unquoted):]

    return path.strip("/")

# === LISTAR NOTAS ===
@app.route("/notes")
def list_notes():

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

    # Remove espaços extras que podem vir no nome do arquivo
    filename = filename.strip()

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
    max_results = int(request.args.get("limit", "30"))  # Evita travamento com muitos arquivos

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
                if len(matches) >= max_results:
                    break
        except Exception:
            continue

    return jsonify({"matches": matches})

# === CRIAR OU ATUALIZAR NOTA ===
@app.route("/note", methods=["POST"])
def create_or_update_note():
    if not request.is_json:
        return jsonify({"error": "Corpo da requisi\u00e7\u00e3o deve ser JSON"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "JSON inv\u00e1lido"}), 400

    filename = data.get("filename")
    content = data.get("content", "")

    if not filename:
        return jsonify({"error": "O campo 'filename' é obrigatório"}), 400

    # Corrigir se o filename vier com prefixo WebDAV completo
    if "remote.php/dav/files" in filename:
        filename = to_relative_path(filename)

    # Remove espaços extras enviados no JSON
    filename = filename.strip()

    file_url = WEBDAV_BASE_URL + quote(filename)
    headers = {"Content-Type": "text/markdown"}
    res = requests.put(
        file_url,
        data=content.encode("utf-8"),
        auth=AUTH,
        headers=headers,
    )

    if res.status_code in [200, 201, 204]:
        return jsonify({"message": "Nota salva com sucesso"})
    else:
        return jsonify({"error": f"Erro ao salvar nota: {res.status_code}"}), 500

# === INICIAR APLICATIVO ===
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
