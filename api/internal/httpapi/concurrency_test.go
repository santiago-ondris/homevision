package httpapi

import (
	"bytes"
	"context"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/santiago-ondris/homevision/api/internal/detector"
)

type limiterCase struct {
	name   string
	slots  int
	cancel bool
}

func TestDetect_LimitsConcurrentCallsAndReleasesSlots(t *testing.T) {
	tests := []limiterCase{{"one slot", 1, false}, {"two slots", 2, false}, {"cancelled requests", 2, true}}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			runLimiterCase(t, test)
		})
	}
}

type unreadableBody struct{}

func runLimiterCase(t *testing.T, test limiterCase) {
	settings := testSettings()
	settings.MaxInFlight = test.slots
	entered := make(chan struct{}, test.slots)
	release := make(chan struct{})
	finished := make(chan *httptest.ResponseRecorder, test.slots)
	var logs bytes.Buffer
	router := NewRouter(settings, blockedDetector(entered, release), slog.New(slog.NewJSONHandler(&logs, nil)))
	cancellations := startBlockedRequests(t, router, test.slots, finished)
	for range test.slots {
		<-entered
	}
	assertOverloaded(t, router)
	if test.cancel {
		for _, cancel := range cancellations {
			cancel()
		}
	} else {
		close(release)
	}
	assertCompletedRequests(t, finished, test)
	if test.cancel {
		close(release)
	}
	accepted := httptest.NewRecorder()
	router.ServeHTTP(accepted, imageRequest(t))
	if accepted.Code != 200 {
		t.Fatalf("after release = %d", accepted.Code)
	}
	for _, cancel := range cancellations {
		cancel()
	}
	if test.cancel {
		assertCancelledLogs(t, &logs, test.slots)
	}
}

func (unreadableBody) Read([]byte) (int, error) { panic("overloaded handler read the body") }

func blockedDetector(entered chan struct{}, release chan struct{}) fakeDetector {
	return fakeDetector{detect: func(ctx context.Context) (detector.Result, error) {
		entered <- struct{}{}
		select {
		case <-release:
			return detector.Result{}, nil
		case <-ctx.Done():
			return detector.Result{}, ctx.Err()
		}
	}}
}

func assertOverloaded(t *testing.T, router http.Handler) {
	t.Helper()
	busy := httptest.NewRequest("POST", "/detect", unreadableBody{})
	resp := httptest.NewRecorder()
	router.ServeHTTP(resp, busy)
	assertErrorResponse(t, resp, 503, "overloaded")
	if resp.Header().Get("Retry-After") != "1" {
		t.Errorf("Retry-After = %q", resp.Header().Get("Retry-After"))
	}
}

func startBlockedRequests(t *testing.T, router http.Handler, slots int, finished chan *httptest.ResponseRecorder) []context.CancelFunc {
	cancellations := make([]context.CancelFunc, 0, slots)
	for range slots {
		req := imageRequest(t)
		ctx, cancel := context.WithCancel(req.Context())
		cancellations = append(cancellations, cancel)
		req = req.WithContext(ctx)
		go func() { resp := httptest.NewRecorder(); router.ServeHTTP(resp, req); finished <- resp }()
	}
	return cancellations
}

func assertCompletedRequests(t *testing.T, finished chan *httptest.ResponseRecorder, test limiterCase) {
	for range test.slots {
		completed := <-finished
		if test.cancel {
			if completed.Body.Len() != 0 {
				t.Errorf("cancelled response = %s", completed.Body.String())
			}
		} else if completed.Code != 200 {
			t.Errorf("completed status = %d", completed.Code)
		}
	}
}

func assertCancelledLogs(t *testing.T, logs *bytes.Buffer, slots int) {
	entries := readLogs(t, logs)
	cancelledCount := 0
	for _, entry := range entries {
		if entry["status"] == float64(499) {
			cancelledCount++
		}
	}
	if cancelledCount != slots {
		t.Fatalf("499 logs = %d", cancelledCount)
	}
}
