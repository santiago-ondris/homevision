# Checkbox detection

Finds checkboxes in a form image and reports which are marked.
A Go API validates uploads, and a Python worker processes images with OpenCV.

- Live page: <https://homevision-dm5.pages.dev>
- Approach, tradeoffs and limitations: [WRITEUP.md](WRITEUP.md)

## Run

Docker is the only requirement.

```sh
docker compose up --build
```

The API runs at <http://localhost:8080>, and the page runs at <http://localhost:5173>.

```sh
curl -s -F "file=@samples/sample2.jpg" localhost:8080/detect
```

```json
{
  "boxes": [
    { "bbox": [156, 96, 179, 120], "is_checked": false },
    { "bbox": [282, 96, 306, 120], "is_checked": true }
  ]
}
```

This sample returns 41 boxes; these are the first two.

- The image goes in a form field named `file`. PNG or JPEG, up to 20 MB.
- `bbox` uses image pixels. `(x1, y1)` is the top-left pixel of the printed border, and `(x2, y2)` is exclusive, so width equals `x2 - x1`.
- Errors are JSON: `{"error": {"code": "...", "message": "..."}}`.

## Evaluate

```sh
docker compose run --rm eval
```

Compares the detector against 288 hand-annotated boxes across four sample images.

```
image          annotated  detected  matched  recall  precision  mean IoU    labels
sample1.png          118       119      118  100.0%      99.2%      0.98   118/118
sample2.jpg           43        41       41   95.3%     100.0%      0.98     40/41
sample3.png           48        48       48  100.0%     100.0%      0.99     48/48
sample4.png           79        78       78   98.7%     100.0%      0.98     78/78
total                288       286      285   99.0%      99.7%      0.98   284/285
```

The parameters were tuned on these same images, so this is an upper bound, not a prediction for unseen forms. The command also lists every miss and wrong label.

## Development

`make lint` and `make test` require Go 1.27, Node.js 24, and an active Python 3.14 virtual environment.

```sh
python3.14 -m venv worker/.venv        # Windows: py -3.14 -m venv worker/.venv
source worker/.venv/bin/activate       # Windows: source worker/.venv/Scripts/activate
python -m pip install -r worker/requirements.txt -r worker/requirements-dev.txt
(cd web && npm ci)
(cd api && go install github.com/golangci/golangci-lint/v2/cmd/golangci-lint@v2.14.0)
```

## What production would need

- Use object storage for uploads instead of request bodies.
- Add a queue between the API and the worker for batch documents.
- Add authentication and per-client rate limits.
- Add metrics and tracing across both services.
- Add worker autoscaling on CPU.
