import json
from unittest.mock import patch

import pytest

from obsidian_api import app, WEBDAV_BASE_URL

BASE_PATH = WEBDAV_BASE_URL.replace("https://cloud.barch.com.br", "")

class DummyResponse:
    def __init__(self, status_code=200, text="", content=b""):
        self.status_code = status_code
        self.text = text
        self.content = content or text.encode("utf-8")

def propfind_response():
    xml = f"""<?xml version='1.0'?>
    <d:multistatus xmlns:d='DAV:'>
        <d:response><d:href>{BASE_PATH}Note1.md</d:href></d:response>
        <d:response><d:href>{BASE_PATH}folder/SubNote.md</d:href></d:response>
    </d:multistatus>"""
    return DummyResponse(status_code=207, content=xml.encode("utf-8"))

def note_response(content="Content"):
    return DummyResponse(status_code=200, text=content)

def put_response():
    return DummyResponse(status_code=201)

def propfind_many_response(count):
    xml = "<?xml version='1.0'?><d:multistatus xmlns:d='DAV:'>"
    for i in range(count):
        xml += f"<d:response><d:href>{BASE_PATH}Note{i}.md</d:href></d:response>"
    xml += "</d:multistatus>"
    return DummyResponse(status_code=207, content=xml.encode("utf-8"))

def malformed_propfind_response():
    """Return a malformed XML response for PROPFIND requests."""
    return DummyResponse(status_code=207, content=b"<badxml>")

@pytest.fixture
def client():
    with app.test_client() as client:
        yield client

def test_list_notes(client):
    with patch("obsidian_api.requests.request", return_value=propfind_response()):
        resp = client.get("/notes")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {
        "files": [
            {"name": "Note1.md", "path": "Note1.md", "folder": ""},
            {"name": "SubNote.md", "path": "folder/SubNote.md", "folder": "folder"},
        ]
    }

def test_list_folders(client):
    with patch("obsidian_api.requests.request", return_value=propfind_response()):
        resp = client.get("/folders")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data == {"folders": ["", "folder"]}

def test_get_note(client):
    with patch("obsidian_api.requests.get", return_value=note_response("Hello")):
        resp = client.get("/note/Note1.md")
    assert resp.status_code == 200
    assert resp.get_json() == {"content": "Hello"}

def test_create_note(client):
    with patch("obsidian_api.requests.put", return_value=put_response()):
        resp = client.post(
            "/note",
            json={"filename": "New.md", "content": "Hi"},
        )
    assert resp.status_code == 200
    assert resp.get_json() == {"message": "Nota salva com sucesso"}


def test_get_note_not_found(client):
    """Return 404 when the note does not exist."""
    with patch("obsidian_api.requests.get", return_value=DummyResponse(status_code=404)):
        resp = client.get("/note/Missing.md")
    assert resp.status_code == 404
    assert resp.get_json() == {"error": "Nota não encontrada"}


def test_create_note_missing_filename(client):
    """Validate error when filename field is absent."""
    with patch("obsidian_api.requests.put") as mock_put:
        resp = client.post("/note", json={"content": "Hi"})
    mock_put.assert_not_called()
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "O campo 'filename' é obrigatório"}


def test_search_notes_limit(client):
    with patch(
        "obsidian_api.requests.request",
        return_value=propfind_many_response(35),
    ), patch(
        "obsidian_api.requests.get",
        return_value=note_response("match term"),
    ) as mock_get:
        # Call the view directly with query args to avoid client routing limits
        from obsidian_api import request as flask_request, search_notes

        flask_request.args = {"term": "match"}
        resp = search_notes()

    assert resp.status_code == 200
    data = resp.get_json()
    expected = [
        {"name": f"Note{i}.md", "path": f"Note{i}.md", "folder": ""}
        for i in range(30)
    ]
    assert data == {"matches": expected}
    assert mock_get.call_count == 30


def test_list_notes_malformed_xml(client):
    """Return 500 when the PROPFIND response contains malformed XML."""
    with patch(
        "obsidian_api.requests.request", return_value=malformed_propfind_response()
    ):
        resp = client.get("/notes")
    assert resp.status_code == 500
    assert resp.get_json() == {"error": "Resposta WebDAV malformada"}
