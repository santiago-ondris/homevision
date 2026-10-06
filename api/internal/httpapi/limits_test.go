package httpapi

import (
	"bytes"
	"image"
	"image/png"
	"io"
	"log/slog"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestDetect_ReportsKnownDimensionsAndConfiguredLimits(t *testing.T) {
	tests := []struct {
		name                string
		width, height, side int
		pixels              int64
		message             string
	}{
		{"side limit", 12, 9, 10, 1000, "The image is 12 × 9 px. The limit is 10 px per side."},
		{"pixel limit", 8, 9, 10, 70, "The image is 8 × 9 px (72 pixels). The limit is 70 pixels."},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			settings := testSettings()
			settings.MaxImageSide = test.side
			settings.MaxImagePixels = test.pixels
			var picture bytes.Buffer
			if err := png.Encode(&picture, image.NewRGBA(image.Rect(0, 0, test.width, test.height))); err != nil {
				t.Fatal(err)
			}
			router := NewRouter(settings, fakeDetector{}, slog.New(slog.NewJSONHandler(io.Discard, nil)))
			resp := httptest.NewRecorder()
			router.ServeHTTP(resp, uploadRequest(t, picture.Bytes()))
			assertErrorResponse(t, resp, 422, "invalid_image")
			if !strings.Contains(resp.Body.String(), test.message) {
				t.Fatalf("body = %s", resp.Body.String())
			}
		})
	}
}

func TestDetect_ReportsByteLimitWithoutInventingFileSize(t *testing.T) {
	tests := []struct {
		name    string
		limit   int64
		body    []byte
		message string
	}{
		{"file cap", bytesPerMegabyte, bytes.Repeat([]byte("x"), bytesPerMegabyte+1), "The file is larger than the 1 MB limit."},
		{"body cap", bytesPerMegabyte, bytes.Repeat([]byte("x"), 3*bytesPerMegabyte), "The file is larger than the 1 MB limit."},
		{"default byte limit", 20 * bytesPerMegabyte, bytes.Repeat([]byte("x"), 20*bytesPerMegabyte+1), "The file is larger than the 20 MB limit."},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			settings := testSettings()
			settings.MaxUploadBytes = test.limit
			router := NewRouter(settings, fakeDetector{}, slog.New(slog.NewJSONHandler(io.Discard, nil)))
			resp := httptest.NewRecorder()
			router.ServeHTTP(resp, uploadRequest(t, test.body))
			assertErrorResponse(t, resp, 413, "file_too_large")
			if resp.Body.String() != `{"error":{"code":"file_too_large","message":"`+test.message+`"}}` {
				t.Fatalf("body = %s", resp.Body.String())
			}
		})
	}
}
