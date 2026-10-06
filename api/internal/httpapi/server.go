package httpapi

import (
	"context"
	"errors"
	"fmt"
	"log/slog"
	"net/http"
	"time"

	"github.com/santiago-ondris/homevision/api/internal/config"
)

const (
	readHeaderTimeout = 5 * time.Second
	readTimeout       = 30 * time.Second
	writeAllowance    = 10 * time.Second
	idleTimeout       = 60 * time.Second
	shutdownTimeout   = 15 * time.Second
)

// NewServer sets the address and HTTP timeouts for the public API.
func NewServer(settings config.Config, handler http.Handler) *http.Server {
	return &http.Server{
		Addr:              fmt.Sprintf(":%d", settings.Port),
		Handler:           handler,
		ReadHeaderTimeout: readHeaderTimeout,
		ReadTimeout:       readTimeout,
		WriteTimeout:      settings.WorkerTimeout + writeAllowance,
		IdleTimeout:       idleTimeout,
	}
}

// Serve runs the server and drains active requests when the context is cancelled.
func Serve(ctx context.Context, server *http.Server, logger *slog.Logger) error {
	finished := make(chan error, 1)
	go func() { finished <- server.ListenAndServe() }()
	select {
	case err := <-finished:
		if errors.Is(err, http.ErrServerClosed) {
			return nil
		}
		return fmt.Errorf("serving HTTP: %w", err)
	case <-ctx.Done():
		shutdown, cancel := context.WithTimeout(context.Background(), shutdownTimeout)
		defer cancel()
		if err := server.Shutdown(shutdown); err != nil {
			logger.Error("draining requests", "error", err)
			if err := server.Close(); err != nil {
				logger.Error("closing server", "error", err)
			}
		}
		if err := <-finished; !errors.Is(err, http.ErrServerClosed) {
			return fmt.Errorf("stopping HTTP server: %w", err)
		}
		return nil
	}
}
