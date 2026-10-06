package httpapi

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"image"
	"image/png"
	"io"
	"log/slog"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"regexp"
	"strings"
	"testing"
	"time"

	"github.com/santiago-ondris/homevision/api/internal/config"
	"github.com/santiago-ondris/homevision/api/internal/detector"
	"github.com/santiago-ondris/homevision/api/internal/requestid"
	"github.com/santiago-ondris/homevision/api/internal/upload"
)

func testSettings() config.Config {
	return config.Config{MaxUploadBytes: 1024, MaxImageSide: 10, MaxImagePixels: 100, MaxInFlight: 2, WorkerTimeout: 20 * time.Second, AllowedOrigins: []string{"http://localhost:5173"}}
}

type fakeDetector struct {
	detect func(context.Context) (detector.Result, error)
	ready  func(context.Context) error
}

func (fake fakeDetector) Detect(ctx context.Context, _ upload.Image) (detector.Result, error) {
	if fake.detect != nil {
		return fake.detect(ctx)
	}
	return detector.Result{}, nil
}
func (fake fakeDetector) Ready(ctx context.Context) error {
	if fake.ready != nil {
		return fake.ready(ctx)
	}
	return nil
}

type detectCase struct {
	name  string
	boxes []detector.Box
	body  string
}

func TestDetect_ReturnsExactPublicResponseAndMetadata(t *testing.T) {
	tests := []detectCase{
		{"boxes", []detector.Box{{BBox: [4]int{1, 2, 3, 4}, IsChecked: true, FillRatio: 0.2}}, `{"boxes":[{"bbox":[1,2,3,4],"is_checked":true}]}`},
		{"empty result", nil, `{"boxes":[]}`},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			runDetectCase(t, test)
		})
	}
}

func runDetectCase(t *testing.T, test detectCase) {
	var logs bytes.Buffer
	fake := fakeDetector{detect: func(ctx context.Context) (detector.Result, error) {
		if requestid.RequestID(ctx) != "detect_1" {
			t.Errorf("worker request id = %q", requestid.RequestID(ctx))
		}
		if _, exists := ctx.Deadline(); !exists {
			t.Error("worker context has no deadline")
		}
		return detector.Result{Boxes: test.boxes}, nil
	}}
	router := NewRouter(testSettings(), fake, slog.New(slog.NewJSONHandler(&logs, nil)))
	req := imageRequest(t)
	req.Header.Set("X-Request-Id", "detect_1")
	resp := httptest.NewRecorder()
	router.ServeHTTP(resp, req)
	if resp.Code != 200 || resp.Body.String() != test.body {
		t.Fatalf("response = %d %s", resp.Code, resp.Body.String())
	}
	if resp.Header().Get("Content-Type") != "application/json" || resp.Header().Get("X-Request-Id") != "detect_1" {
		t.Fatalf("headers = %v", resp.Header())
	}
	if !regexp.MustCompile(`^detect;dur=[0-9]+\.[0-9]{3}, total;dur=[0-9]+\.[0-9]{3}$`).MatchString(resp.Header().Get("Server-Timing")) {
		t.Fatalf("timing = %q", resp.Header().Get("Server-Timing"))
	}
	var entry map[string]any
	if err := json.Unmarshal(bytes.TrimSpace(logs.Bytes()), &entry); err != nil {
		t.Fatal(err)
	}
	for _, field := range []string{"request_id", "method", "path", "status", "duration_ms", "bytes_in", "bytes_out", "width", "height", "format", "boxes", "worker_ms"} {
		if _, found := entry[field]; !found {
			t.Errorf("missing log field %s", field)
		}
	}
	if entry["status"] != float64(200) || entry["bytes_in"] != float64(req.ContentLength) || entry["bytes_out"] != float64(len(test.body)) || entry["boxes"] != float64(len(test.boxes)) || entry["width"] != float64(3) || entry["height"] != float64(2) || entry["format"] != "image/png" {
		t.Fatalf("access log = %v", entry)
	}
}

type errorCase struct {
	name, method, path string
	body               []byte
	workerError        error
	status             int
	code               string
	limit              int64
	panic              bool
	allow              string
}

func TestRouter_MapsErrorsToJSON(t *testing.T) {
	tests := []errorCase{
		{name: "missing multipart", method: "POST", path: "/detect", status: 400, code: "invalid_request"},
		{name: "file too large", method: "POST", path: "/detect", status: 413, code: "file_too_large", limit: 1},
		{name: "unsupported format", method: "POST", path: "/detect", body: []byte("text"), status: 415, code: "unsupported_media_type"},
		{name: "invalid image", method: "POST", path: "/detect", body: []byte{0xff, 0xd8, 0xff}, status: 422, code: "invalid_image"},
		{name: "unexpected error", method: "POST", path: "/detect", workerError: errors.New("private details"), status: 500, code: "internal_error"},
		{name: "worker unavailable", method: "POST", path: "/detect", workerError: detector.ErrUnavailable, status: 503, code: "detector_unavailable"},
		{name: "worker timeout", method: "POST", path: "/detect", workerError: detector.ErrTimeout, status: 504, code: "detector_timeout"},
		{name: "worker size rejection", method: "POST", path: "/detect", workerError: &detector.RejectedError{Status: 413, Code: "file_too_large", Message: "The file is larger than the 20 MB limit."}, status: 413, code: "file_too_large"},
		{name: "worker format rejection", method: "POST", path: "/detect", workerError: &detector.RejectedError{Status: 415, Code: "unsupported_media_type", Message: "Send a PNG or JPEG image."}, status: 415, code: "unsupported_media_type"},
		{name: "worker image rejection", method: "POST", path: "/detect", workerError: &detector.RejectedError{Status: 422, Code: "invalid_image", Message: "The image could not be decoded."}, status: 422, code: "invalid_image"},
		{name: "unknown path", method: "GET", path: "/missing", status: 404, code: "not_found"},
		{name: "wrong detect method", method: "GET", path: "/detect", status: 405, code: "method_not_allowed", allow: "POST, OPTIONS"},
		{name: "wrong health method", method: "POST", path: "/healthz", status: 405, code: "method_not_allowed", allow: "GET"},
		{name: "HEAD is not GET", method: "HEAD", path: "/healthz", status: 405, code: "method_not_allowed", allow: "GET"},
		{name: "wrong ready method", method: "PUT", path: "/readyz", status: 405, code: "method_not_allowed", allow: "GET"},
		{name: "panic", method: "POST", path: "/detect", panic: true, status: 500, code: "internal_error"},
		{name: "unready", method: "GET", path: "/readyz", workerError: detector.ErrTimeout, status: 503, code: "detector_unavailable"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			runErrorCase(t, test)
		})
	}
}

func runErrorCase(t *testing.T, test errorCase) {
	settings := testSettings()
	if test.limit != 0 {
		settings.MaxUploadBytes = test.limit
	}
	var logs bytes.Buffer
	fake := fakeDetector{detect: func(context.Context) (detector.Result, error) {
		if test.panic {
			panic("detector panic")
		}
		return detector.Result{}, test.workerError
	}, ready: func(context.Context) error { return test.workerError }}
	router := NewRouter(settings, fake, slog.New(slog.NewJSONHandler(&logs, nil)))
	req := test.request(t)
	resp := httptest.NewRecorder()
	router.ServeHTTP(resp, req)
	assertErrorResponse(t, resp, test.status, test.code)
	if resp.Header().Get("Allow") != test.allow {
		t.Fatalf("Allow = %q", resp.Header().Get("Allow"))
	}
	if strings.Contains(resp.Body.String(), "private details") || strings.Contains(resp.Body.String(), "detector panic") {
		t.Fatalf("response leaks failure: %s", resp.Body.String())
	}
	if test.workerError != nil {
		var rejected *detector.RejectedError
		if errors.As(test.workerError, &rejected) && !strings.Contains(resp.Body.String(), rejected.Message) {
			t.Fatalf("worker message not preserved: %s", resp.Body.String())
		}
	}
	test.assertLog(t, &logs, resp)
}

func (test errorCase) request(t *testing.T) *http.Request {
	var req *http.Request
	if test.method == "POST" && test.path == "/detect" && test.name != "missing multipart" {
		if test.body != nil {
			req = uploadRequest(t, test.body)
		} else {
			req = imageRequest(t)
		}
	} else {
		req = httptest.NewRequest(test.method, test.path, nil)
	}
	return req
}

func (test errorCase) assertLog(t *testing.T, logs *bytes.Buffer, resp *httptest.ResponseRecorder) {
	logContent := logs.String()
	entries := readLogs(t, logs)
	completed := 0
	for _, entry := range entries {
		if entry["request_id"] != resp.Header().Get("X-Request-Id") {
			t.Errorf("log request id = %v", entry["request_id"])
		}
		if entry["msg"] == "request completed" {
			completed++
			if entry["status"] != float64(test.status) || entry["bytes_out"] != float64(resp.Body.Len()) {
				t.Errorf("access log = %v", entry)
			}
		}
	}
	if completed != 1 {
		t.Fatalf("access log count = %d", completed)
	}
	if test.panic && !strings.Contains(logContent, `"stack"`) {
		t.Error("panic stack was not logged")
	}
}

type routeCase struct {
	name, method, path, origin, id string
	status                         int
	allowed                        bool
}

func TestRouter_HandlesHealthCORSAndRequestIDs(t *testing.T) {
	tests := []routeCase{
		{"health", "GET", "/healthz", "", "", 200, false},
		{"ready", "GET", "/readyz", "", "", 200, false},
		{"allowed origin", "GET", "/healthz", "http://localhost:5173", "", 200, true},
		{"disallowed origin", "GET", "/healthz", "http://other.example", "", 200, false},
		{"preflight", "OPTIONS", "/detect", "http://localhost:5173", "", 204, true},
		{"disallowed preflight", "OPTIONS", "/detect", "http://other.example", "", 204, false},
		{"valid id", "GET", "/healthz", "", "valid-id_1", 200, false},
		{"invalid id", "GET", "/healthz", "", "invalid id", 200, false},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			runRouteCase(t, test)
		})
	}
}

func runRouteCase(t *testing.T, test routeCase) {
	router := NewRouter(testSettings(), fakeDetector{}, slog.New(slog.NewJSONHandler(io.Discard, nil)))
	req := httptest.NewRequest(test.method, test.path, nil)
	req.Header.Set("Origin", test.origin)
	req.Header.Set("X-Request-Id", test.id)
	resp := httptest.NewRecorder()
	router.ServeHTTP(resp, req)
	if resp.Code != test.status {
		t.Fatalf("status = %d", resp.Code)
	}
	id := resp.Header().Get("X-Request-Id")
	if !regexp.MustCompile(requestIDPattern).MatchString(id) {
		t.Fatalf("request id = %q", id)
	}
	if test.id == "valid-id_1" && id != test.id {
		t.Fatalf("id = %q", id)
	}
	if test.id == "invalid id" && id == test.id {
		t.Fatalf("invalid id echoed")
	}
	if test.status == 200 && resp.Body.String() != `{"status":"ok"}` {
		t.Fatalf("body = %s", resp.Body.String())
	}
	if test.allowed {
		if resp.Header().Get("Access-Control-Allow-Origin") != test.origin || resp.Header().Get("Access-Control-Expose-Headers") != "X-Request-Id, Server-Timing" {
			t.Fatalf("CORS headers = %v", resp.Header())
		}
		if test.method == "OPTIONS" && (resp.Header().Get("Access-Control-Allow-Methods") != "POST, OPTIONS" || resp.Header().Get("Access-Control-Allow-Headers") != "Content-Type, X-Request-Id" || resp.Body.Len() != 0) {
			t.Fatalf("preflight = %v %s", resp.Header(), resp.Body.String())
		}
	} else {
		for name := range resp.Header() {
			if strings.HasPrefix(name, "Access-Control-") {
				t.Errorf("unexpected CORS header %s", name)
			}
		}
	}
}

func assertErrorResponse(t *testing.T, resp *httptest.ResponseRecorder, status int, code string) {
	t.Helper()
	if resp.Code != status || resp.Header().Get("Content-Type") != "application/json" || resp.Header().Get("X-Request-Id") == "" {
		t.Fatalf("response = %d %v %s", resp.Code, resp.Header(), resp.Body.String())
	}
	var body map[string]map[string]string
	if err := json.Unmarshal(resp.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if len(body) != 1 || len(body["error"]) != 2 || body["error"]["code"] != code || body["error"]["message"] == "" {
		t.Fatalf("error body = %s", resp.Body.String())
	}
}

func imageRequest(t *testing.T) *http.Request {
	t.Helper()
	var buffer bytes.Buffer
	if err := png.Encode(&buffer, image.NewRGBA(image.Rect(0, 0, 3, 2))); err != nil {
		t.Fatal(err)
	}
	return uploadRequest(t, buffer.Bytes())
}

func uploadRequest(t *testing.T, data []byte) *http.Request {
	t.Helper()
	var buffer bytes.Buffer
	writer := multipart.NewWriter(&buffer)
	part, err := writer.CreateFormFile("file", "image.png")
	if err != nil {
		t.Fatal(err)
	}
	if _, err := part.Write(data); err != nil {
		t.Fatal(err)
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest("POST", "/detect", &buffer)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	return req
}

func readLogs(t *testing.T, buffer *bytes.Buffer) []map[string]any {
	t.Helper()
	var entries []map[string]any
	decoder := json.NewDecoder(buffer)
	for {
		var entry map[string]any
		err := decoder.Decode(&entry)
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			t.Fatal(err)
		}
		entries = append(entries, entry)
	}
	return entries
}
