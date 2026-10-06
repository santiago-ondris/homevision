// Package main starts the HTTP API.
package main

import (
	"fmt"
	"log/slog"
	"net/http"
	"os"

	"github.com/santiago-ondris/homevision/api/internal/config"
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
	port, err := config.LoadPort()
	if err != nil {
		return fmt.Errorf("loading configuration: %w", err)
	}
	server := &http.Server{
		Addr:    fmt.Sprintf(":%d", port),
		Handler: httpapi.NewRouter(logger),
	}
	logger.Info("server listening", "port", port)
	if err := server.ListenAndServe(); err != nil {
		return fmt.Errorf("serving HTTP: %w", err)
	}
	return nil
}
