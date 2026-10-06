// Package main starts the HTTP API.
package main

import (
	"context"
	"fmt"
	"log/slog"
	"os"
	"os/signal"
	"syscall"

	"github.com/santiago-ondris/homevision/api/internal/config"
	"github.com/santiago-ondris/homevision/api/internal/detector"
	"github.com/santiago-ondris/homevision/api/internal/httpapi"
)

func main() {
	logger := slog.New(slog.NewJSONHandler(os.Stdout, nil))
	if err := run(logger); err != nil {
		logger.Error("server stopped", "error", err)
		os.Exit(1)
	}
}

func run(logger *slog.Logger) error {
	settings, err := config.Load()
	if err != nil {
		return fmt.Errorf("loading configuration: %w", err)
	}
	client := detector.New(settings.WorkerURL, settings.WorkerTimeout)
	server := httpapi.NewServer(settings, httpapi.NewRouter(settings, client, logger))
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	logger.Info(
		"server starting",
		"port",
		settings.Port,
		"max_upload_bytes",
		settings.MaxUploadBytes,
		"max_image_side",
		settings.MaxImageSide,
		"max_image_pixels",
		settings.MaxImagePixels,
		"worker_url",
		settings.WorkerURL,
		"worker_timeout",
		settings.WorkerTimeout.String(),
		"max_in_flight",
		settings.MaxInFlight,
		"allowed_origins",
		settings.AllowedOrigins,
	)
	return httpapi.Serve(ctx, server, logger)
}
