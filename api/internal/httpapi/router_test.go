package httpapi

import (
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestHealth_ReturnsOK(t *testing.T) {
	tests := []struct {
		name string
		id   string
	}{
		{name: "generated request identifier"},
		{name: "accepted request identifier", id: "health-check_1"},
		{name: "invalid request identifier", id: "invalid identifier"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			logger := slog.New(slog.NewJSONHandler(io.Discard, nil))
			req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
			req.Header.Set("X-Request-Id", test.id)
			resp := httptest.NewRecorder()
			NewRouter(logger).ServeHTTP(resp, req)

			if resp.Code != http.StatusOK {
				t.Fatalf("status = %d, want %d", resp.Code, http.StatusOK)
			}
			if resp.Body.String() != `{"status":"ok"}` {
				t.Fatalf("body = %q", resp.Body.String())
			}
			if resp.Header().Get("Content-Type") != "application/json" {
				t.Fatalf("content type = %q", resp.Header().Get("Content-Type"))
			}
			id := resp.Header().Get("X-Request-Id")
			if id == "" || id == "invalid identifier" {
				t.Fatalf("request identifier = %q", id)
			}
			if test.id == "health-check_1" && id != test.id {
				t.Fatalf("request identifier = %q, want %q", id, test.id)
			}
		})
	}
}
