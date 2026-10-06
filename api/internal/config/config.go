// Package config reads and validates API configuration.
package config

import (
	"fmt"
	"net/url"
	"os"
	"strconv"
	"strings"
	"time"
)

const (
	defaultPort          = 8080
	maximumPort          = 65535
	defaultUploadBytes   = 20971520
	defaultImageSide     = 10000
	defaultImagePixels   = 40000000
	defaultInFlight      = 4
	defaultWorkerURL     = "http://worker:8000"
	defaultWorkerTimeout = 20 * time.Second
	defaultOrigins       = "http://localhost:5173"
)

// Config holds the validated API settings.
type Config struct {
	Port           int
	MaxUploadBytes int64
	MaxImageSide   int
	MaxImagePixels int64
	WorkerURL      string
	WorkerTimeout  time.Duration
	MaxInFlight    int
	AllowedOrigins []string
}

// Load reads the environment and rejects invalid settings.
func Load() (Config, error) {
	settings, err := loadNumbers()
	if err != nil {
		return Config{}, err
	}
	settings.WorkerURL, err = loadWorkerURL()
	if err != nil {
		return Config{}, err
	}
	settings.WorkerTimeout, err = loadWorkerTimeout()
	if err != nil {
		return Config{}, err
	}
	settings.AllowedOrigins, err = origins(environment("ALLOWED_ORIGINS", defaultOrigins))
	if err != nil {
		return Config{}, err
	}
	return settings, nil
}

func loadNumbers() (Config, error) {
	var settings Config
	var port, side, inFlight int64
	integers := []struct {
		name     string
		fallback int64
		target   *int64
	}{
		{
			name:     "PORT",
			fallback: defaultPort,
			target:   &port,
		},
		{
			name:     "MAX_UPLOAD_BYTES",
			fallback: defaultUploadBytes,
			target:   &settings.MaxUploadBytes,
		},
		{
			name:     "MAX_IMAGE_SIDE",
			fallback: defaultImageSide,
			target:   &side,
		},
		{
			name:     "MAX_IMAGE_PIXELS",
			fallback: defaultImagePixels,
			target:   &settings.MaxImagePixels,
		},
		{
			name:     "MAX_IN_FLIGHT",
			fallback: defaultInFlight,
			target:   &inFlight,
		},
	}
	for _, setting := range integers {
		value, err := positiveInteger(setting.name, setting.fallback)
		if err != nil {
			return Config{}, err
		}
		*setting.target = value
	}
	if port > maximumPort {
		return Config{}, fmt.Errorf("PORT must be between 1 and %d", maximumPort)
	}
	settings.Port = int(port)
	settings.MaxImageSide = int(side)
	settings.MaxInFlight = int(inFlight)
	return settings, nil
}

func loadWorkerURL() (string, error) {
	value := environment("WORKER_URL", defaultWorkerURL)
	parsed, err := url.Parse(value)
	if err != nil {
		return "", fmt.Errorf("parsing WORKER_URL: %w", err)
	}
	if parsed.Scheme == "" || parsed.Hostname() == "" {
		return "", fmt.Errorf("WORKER_URL must include a scheme and host")
	}
	return value, nil
}

func loadWorkerTimeout() (time.Duration, error) {
	value, err := time.ParseDuration(environment("WORKER_TIMEOUT", defaultWorkerTimeout.String()))
	if err != nil {
		return 0, fmt.Errorf("parsing WORKER_TIMEOUT: %w", err)
	}
	if value <= 0 {
		return 0, fmt.Errorf("WORKER_TIMEOUT must be positive")
	}
	return value, nil
}

func positiveInteger(name string, fallback int64) (int64, error) {
	value, err := strconv.ParseInt(environment(name, strconv.FormatInt(fallback, 10)), 10, 64)
	if err != nil {
		return 0, fmt.Errorf("parsing %s: %w", name, err)
	}
	if value <= 0 {
		return 0, fmt.Errorf("%s must be positive", name)
	}
	return value, nil
}

func environment(name, fallback string) string {
	if value, exists := os.LookupEnv(name); exists {
		return value
	}
	return fallback
}

func origins(value string) ([]string, error) {
	allowed := strings.Split(value, ",")
	for i, origin := range allowed {
		origin = strings.TrimSpace(origin)
		parsed, err := url.Parse(origin)
		if err != nil {
			return nil, fmt.Errorf("parsing ALLOWED_ORIGINS: %w", err)
		}
		if parsed.Scheme == "" ||
			parsed.Hostname() == "" ||
			strings.Contains(origin, "*") ||
			origin != parsed.Scheme+"://"+parsed.Host {
			return nil, fmt.Errorf("ALLOWED_ORIGINS must contain exact origins in scheme://host[:port] form")
		}
		allowed[i] = origin
	}
	return allowed, nil
}
