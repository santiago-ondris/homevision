# Checkbox detection

```sh
docker compose up --build
docker compose run --rm eval
```

## Development

Create and activate a Python 3.14 virtual environment.

macOS and Linux:

```sh
python3.14 -m venv worker/.venv
source worker/.venv/bin/activate
```

Windows (Git Bash):

```sh
py -3.14 -m venv worker/.venv
source worker/.venv/Scripts/activate
```

Install the local dependencies:

```sh
python -m pip install -r worker/requirements.txt -r worker/requirements-dev.txt
(cd web && npm ci)
(cd api && go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.14.0)
```
