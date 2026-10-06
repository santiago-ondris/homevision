// Package httpapi provides the API's HTTP handlers.
package httpapi

import (
	"context"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"github.com/santiago-ondris/homevision/api/internal/config"
	"github.com/santiago-ondris/homevision/api/internal/detector"
	"github.com/santiago-ondris/homevision/api/internal/upload"
)

// Detector supplies checkbox detection and worker readiness.
type Detector interface {
	Detect(ctx context.Context, image upload.Image) (detector.Result, error)
	Ready(ctx context.Context) error
}

type api struct {
	settings config.Config
	detector Detector
	logger   *slog.Logger
	slots    chan struct{}
}

// NewRouter builds the routes, limiter and request middleware.
func NewRouter(settings config.Config, service Detector, logger *slog.Logger) http.Handler {
	server := &api{
		settings: settings,
		detector: service,
		logger:   logger,
		slots:    make(chan struct{}, settings.MaxInFlight),
	}
	router := http.NewServeMux()
	// TODO(prod): authenticate clients and limit requests per client to prevent one caller exhausting capacity.
	router.HandleFunc("POST /detect", server.detect)
	router.HandleFunc("OPTIONS /detect", func(resp http.ResponseWriter, _ *http.Request) {
		resp.WriteHeader(http.StatusNoContent)
	})
	router.HandleFunc("GET /healthz", server.health)
	router.HandleFunc("GET /readyz", server.ready)
	router.HandleFunc("/detect", server.methodNotAllowed("POST, OPTIONS"))
	router.HandleFunc("/healthz", server.methodNotAllowed("GET"))
	router.HandleFunc("/readyz", server.methodNotAllowed("GET"))
	// GET patterns also match HEAD, but these endpoints accept only GET.
	router.HandleFunc("HEAD /healthz", server.methodNotAllowed("GET"))
	router.HandleFunc("HEAD /readyz", server.methodNotAllowed("GET"))
	router.HandleFunc("/", func(resp http.ResponseWriter, req *http.Request) {
		server.writeError(resp, req, &routeError{
			status:  http.StatusNotFound,
			code:    "not_found",
			message: "The requested path was not found.",
		})
	})
	return server.requestID(server.recoverPanic(server.accessLog(server.cors(router))))
}

func (server *api) methodNotAllowed(allow string) http.HandlerFunc {
	return func(resp http.ResponseWriter, req *http.Request) {
		resp.Header().Set("Allow", allow)
		server.writeError(resp, req, &routeError{
			status:  http.StatusMethodNotAllowed,
			code:    "method_not_allowed",
			message: "Use one of the methods listed in the Allow header.",
		})
	}
}

func (server *api) health(resp http.ResponseWriter, req *http.Request) {
	server.writeJSON(resp, req, http.StatusOK, struct {
		Status string `json:"status"`
	}{"ok"})
}

func (server *api) ready(resp http.ResponseWriter, req *http.Request) {
	if err := server.detector.Ready(req.Context()); err != nil {
		server.writeError(resp, req, detector.ErrUnavailable)
		return
	}
	server.health(resp, req)
}

type publicBox struct {
	BBox      [4]int `json:"bbox"`
	IsChecked bool   `json:"is_checked"`
}

type detectResponse struct {
	Boxes []publicBox `json:"boxes"`
}

func (server *api) detect(resp http.ResponseWriter, req *http.Request) {
	select {
	case server.slots <- struct{}{}:
		defer func() { <-server.slots }()
	default:
		resp.Header().Set("Retry-After", "1")
		server.writeError(resp, req, &overloadedError{})
		return
	}
	limits := upload.Limits{
		MaxBytes:  server.settings.MaxUploadBytes,
		MaxSide:   server.settings.MaxImageSide,
		MaxPixels: server.settings.MaxImagePixels,
	}
	picture, err := upload.Read(resp, req, limits)
	if err != nil {
		server.writeError(resp, req, err)
		return
	}
	if req.Context().Err() != nil {
		observation(req).status = clientClosedStatus
		return
	}
	server.detectImage(resp, req, picture)
}

func (server *api) detectImage(resp http.ResponseWriter, req *http.Request, picture upload.Image) {
	// TODO(prod): queue batch documents between API and worker so processing can outlive HTTP requests.
	ctx, cancel := context.WithTimeout(req.Context(), server.settings.WorkerTimeout)
	defer cancel()
	workerStarted := time.Now()
	result, err := server.detector.Detect(ctx, picture)
	workerDuration := time.Since(workerStarted)
	if err != nil {
		server.writeError(resp, req, err)
		return
	}
	if req.Context().Err() != nil {
		observation(req).status = clientClosedStatus
		return
	}
	body := detectResponse{Boxes: make([]publicBox, 0, len(result.Boxes))}
	for _, box := range result.Boxes {
		body.Boxes = append(body.Boxes, publicBox{box.BBox, box.IsChecked})
	}
	record := observation(req)
	record.details = []any{
		"width", picture.Width,
		"height", picture.Height,
		"format", picture.Format,
		"boxes", len(body.Boxes),
		"worker_ms", milliseconds(workerDuration),
	}
	resp.Header().Set("Server-Timing", fmt.Sprintf(
		"detect;dur=%.3f, total;dur=%.3f",
		milliseconds(workerDuration),
		milliseconds(time.Since(record.started)),
	))
	server.writeJSON(resp, req, http.StatusOK, body)
}

func milliseconds(duration time.Duration) float64 {
	return float64(duration) / float64(time.Millisecond)
}
