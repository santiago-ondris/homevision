// Package httpapi provides the API's HTTP handlers.
package httpapi

import (
	"crypto/rand"
	"log/slog"
	"net/http"
	"regexp"
)

const requestIDPattern = `^[A-Za-z0-9_-]{1,64}$`

// NewRouter returns the API's HTTP handler.
func NewRouter(logger *slog.Logger) http.Handler {
	validRequestID := regexp.MustCompile(requestIDPattern)
	router := http.NewServeMux()
	router.HandleFunc("GET /healthz", func(resp http.ResponseWriter, _ *http.Request) {
		resp.Header().Set("Content-Type", "application/json")
		if _, err := resp.Write([]byte(`{"status":"ok"}`)); err != nil {
			logger.Error("writing health response", "request_id", resp.Header().Get("X-Request-Id"), "error", err)
			return
		}
	})
	return http.HandlerFunc(func(resp http.ResponseWriter, req *http.Request) {
		id := req.Header.Get("X-Request-Id")
		if !validRequestID.MatchString(id) {
			id = rand.Text()
		}
		resp.Header().Set("X-Request-Id", id)
		router.ServeHTTP(resp, req)
		logger.Info("request completed", "request_id", id, "method", req.Method, "path", req.URL.Path)
	})
}
