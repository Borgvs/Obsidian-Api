import os
import sys
import logging

# For local tests: allow fallback stubs if needed
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "tests", "stubs"))

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote, unquote, urlparse
from xml.etree import ElementTree

app = Flask(__name__)
CORS(app)

# === LOGGING CONFIG ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === HEALTH CHECK ===
@app.route("/ping")
def ping():
    return jsonify({"status": "ok"})

# === CONFIGURAÇÕES ===
USERNAME = os.environ.get("USERNAME", "gustavo")
PASSWORD = os.environ.get("PASSWORD", "Xkntc-ypdG5-3SL5H-NP2GX-4YC9W")
WEBDAV_BASE_URL = os.environ.get(
    "WEBDAV_BASE_URL",
    "https://cloud.barch.com.br/remote.php/dav/files/Gustavo/Barch%20Adm/03.Recursos/ObsidianVault/Gustavo/",
)
AUTH = HTTPBasicAuth(USERNAME, PASSWORD)
BASE_PATH = unquote(urlparse(WEBDAV_BASE_URL).path)


def to_relative_path(raw_path: str) -> str:
    """Converte o caminho WebDAV completo em um caminho relativo ao cofre."""
    path = unquote(raw_path)
    if path.startswith(BASE_PATH):
        path = path[len(BASE_PATH):]
    return path.strip("/")


def propfind_webdav():
    """Executa PROPFIND e retorna árvore XML ou erro"""
    headers = {"Depth": "infinity"}
    res = requests.request("PROPFIND", WEBDAV_BASE_URL, headers=headers, auth=AUTH)
    if res.status_code != 207:
        return None, f"Erro WebDAV: {res.status_code}"

    try:
        tree = ElementTree.fromstring(res.content)
    except ElementTree.ParseError:
        return None, "Resposta WebDAV malformada"

    return tree, None


# === LISTAR NOTAS ===
@app.route("/notes")
def list_notes():
    query = request.args.get("q", "").lower()
    folder_filter = request.args.get("folder", "")
    limit = int(request.args.get("limit", "100"))

    tree, error = propfind_webdav()
    if error:
        return jsonify({"error": error}), 500

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

    logger.info("/notes chamado, retornando %d resultados", len(notas))
    return jsonify({"files": notas})


# === RETORNAR CONTEÚDO DE UMA NOTA ===
@app.route("/note/<path:filename>")
def get_note(filename):
    if "remote.php/dav/files/" in filename:
        filename = to_relative_path(filename)

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
    tree, error = propfind_webdav()
    if error:
        return jsonify({"error": error}), 500

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

    logger.info("/folders chamado, retornando %d pastas", len(folders))
    return jsonify({"folders": sorted(list(folders))})


# === BUSCAR POR CONTEÚDO ===
@app.route("/search")
def search_notes():
    term = request.args.get("term", "").lower()
    if not term:
        return jsonify({"matches": []})

    max_results = int(request.args.get("limit", "30"))

    tree, error = propfind_webdav()
    if error:
        return jsonify({"error": error}), 500

    matches = []

    for elem in tree.findall(".//{DAV:}href"):
        path = unquote(elem.text)
        if not path.endswith(".md") or "Attachments" in path or "Readwise" in path:
            continue

        rel_path = to_relative_path(elem.text)

        file_url = WEBDAV_BASE_URL + quote(rel_path)
        try:
            file_res = requests.get(file_url, auth=AUTH)
            if file_res.status_code == 200:
                if term in file_res.text.lower():
                    matches.append({
                        "name": os.path.basename(rel_path),
                        "path": rel_path,
                        "folder": os.path.dirname(rel_path)
                    })
                    if len(matches) >= max_results:
                        break
            else:
                logger.warning("Erro ao buscar %s (HTTP %d)", rel_path, file_res.status_code)
        except Exception as e:
            logger.error("Erro ao buscar %s: %s", rel_path, e)
            continue

    logger.info("/search chamado, retornando %d resultados", len(matches))
    return jsonify({"matches": matches})


# === CRIAR OU ATUALIZAR NOTA ===
@app.route("/note", methods=["POST"])
def create_or_update_note():
    if not request.is_json:
        return jsonify({"error": "Corpo da requisição deve ser JSON"}), 400

    data = request.get_json()
    if not isinstance(data, dict):
        return jsonify({"error": "JSON inválido"}), 400

    filename = data.get("filename")
    content = data.get("content", "")

    if not filename:
        return jsonify({"error": "O campo 'filename' é obrigatório"}), 400

    if "remote.php/dav/files" in filename:
        filename = to_relative_path(filename)

    filename = filename.strip()

    file_url = WEBDAV_BASE_URL + quote(filename)
    headers = {"Content-Type": "text/markdown"}

    res = requests.put(file_url, data=content.encode("utf-8"), auth=AUTH, headers=headers)

    if res.status_code in [200, 201, 204]:
        logger.info("/note criado/atualizado: %s", filename)
        return jsonify({"message": "Nota salva com sucesso"})
    else:
        logger.error("Erro ao salvar %s: HTTP %d", filename, res.status_code)
        return jsonify({"error": f"Erro ao salvar nota: {res.status_code}"}), 500


# === INICIAR APLICATIVO ===
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))  # Render define $PORT
    app.run(host="0.0.0.0", port=port)

