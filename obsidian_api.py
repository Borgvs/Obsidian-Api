from flask import Flask, jsonify, Response
import requests
from requests.auth import HTTPBasicAuth
from urllib.parse import quote

app = Flask(__name__)

USERNAME = "gustavo"
PASSWORD = "Xkntc-ypdG5-3SL5H-NP2GX-4YC9W"
WEBDAV_BASE_URL = "https://cloud.barch.com.br/remote.php/dav/files/Gustavo/Barch%20Adm/03.Recursos/ObsidianVault/Gustavo/"

AUTH = HTTPBasicAuth(USERNAME, PASSWORD)

@app.route("/notes")
def list_notes():
    headers = {"Depth": "1"}
    res = requests.request("PROPFIND", WEBDAV_BASE_URL, headers=headers, auth=AUTH)
    if res.status_code != 207:
        return jsonify({"error": "Erro ao acessar o WebDAV"}), 500
    from xml.etree import ElementTree
    tree = ElementTree.fromstring(res.content)
    notas = []
    for elem in tree.findall(".//{DAV:}href"):
        nome = elem.text.split("/")[-1]
        if nome.endswith(".md"):
            notas.append(nome)
    return jsonify(notas)

@app.route("/note/<filename>")
def get_note(filename):
    file_url = WEBDAV_BASE_URL + quote(filename)
    res = requests.get(file_url, auth=AUTH)
    if res.status_code == 200:
        return Response(res.content, mimetype="text/markdown")
    return jsonify({"erro": "Nota não encontrada"}), 404

if __name__ == "__main__":
    app.run(port=5000)
