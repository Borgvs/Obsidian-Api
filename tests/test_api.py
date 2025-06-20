import json
from unittest.mock import patch

import pytest

from obsidian_api import app, BASE_PATH

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
