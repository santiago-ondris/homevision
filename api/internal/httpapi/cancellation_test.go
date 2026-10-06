package httpapi

import (
	"bytes"
	"context"
	"io"
	"log/slog"
	"net/http/httptest"
	"testing"

	"github.com/santiago-ondris/homevision/api/internal/detector"
)

type cancelOnRead struct {
	io.ReadCloser
	cancel context.CancelFunc
}

func (body cancelOnRead) Read(data []byte) (int, error) {
	count, err := body.ReadCloser.Read(data)
	body.cancel()
	return count, err
}

func TestDetect_StopsBeforeCallingWorkerWhenUploadIsCancelled(t *testing.T) {
	tests := []struct {
		name       string
		beforeRead bool
	}{{"before reading upload", true}, {"during upload", false}}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			var logs bytes.Buffer
			called := false
			fake := fakeDetector{detect: func(context.Context) (detector.Result, error) { called = true; return detector.Result{}, nil }}
			router := NewRouter(testSettings(), fake, slog.New(slog.NewJSONHandler(&logs, nil)))
			req := imageRequest(t)
			ctx, cancel := context.WithCancel(req.Context())
			defer cancel()
			req = req.WithContext(ctx)
			if test.beforeRead {
				cancel()
				req.Body = io.NopCloser(unreadableBody{})
			} else {
				req.Body = cancelOnRead{req.Body, cancel}
			}
			resp := httptest.NewRecorder()
			router.ServeHTTP(resp, req)
			if called || resp.Body.Len() != 0 || resp.Header().Get("Content-Type") != "" {
				t.Fatalf("worker called = %v, response = %v %s", called, resp.Header(), resp.Body.String())
			}
			assertCancelledLogs(t, &logs, 1)
		})
	}
}
