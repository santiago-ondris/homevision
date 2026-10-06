// Package config reads and validates API configuration.
package config

import (
	"fmt"
	"os"
	"strconv"
)

const defaultPort = 8080

const minimumPort = 1

const maximumPort = 65535

// LoadPort reads PORT and returns a validated port or the default.
func LoadPort() (int, error) {
	value := os.Getenv("PORT")
	if value == "" {
		return defaultPort, nil
	}
	port, err := strconv.Atoi(value)
	if err != nil {
		return 0, fmt.Errorf("parsing PORT: %w", err)
	}
	if port < minimumPort || port > maximumPort {
		return 0, fmt.Errorf("PORT must be between %d and %d", minimumPort, maximumPort)
	}
	return port, nil
}
