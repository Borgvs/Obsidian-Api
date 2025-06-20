Política de Privacidade – Nora
Nora é uma assistente privada conectada ao seu cofre pessoal do Obsidian via uma API hospedada no Render.

Nenhuma informação é armazenada ou transmitida para terceiros.
O conteúdo acessado vem do seu Nextcloud por meio de WebDAV seguro.
Nenhum dado pessoal é processado ou salvo fora da sessão atual.
Você pode desconectar ou excluir a API a qualquer momento para encerrar o acesso.

## Environment variables

A API utiliza as seguintes variáveis de ambiente para configurar a conexão WebDAV:

- `USERNAME` – nome de usuário do WebDAV
- `PASSWORD` – senha do WebDAV
- `WEBDAV_BASE_URL` – URL base para os arquivos do cofre

Valores padrão de desenvolvimento são usados caso não estejam definidos.

## Running tests

Install the requirements and run `pytest` from the repository root:

```bash
pytest
```
