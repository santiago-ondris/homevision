package config

import (
	"os"
	"reflect"
	"strings"
	"testing"
	"time"
)

func TestLoad_ParsesDefaultsAndOverrides(t *testing.T) {
	tests := []struct {
		name        string
		environment map[string]string
		want        Config
	}{
		{"missing variables", nil, Config{8080, 20971520, 10000, 40000000, "http://worker:8000", 20 * time.Second, 4, []string{"http://localhost:5173"}}},
		{"overrides", map[string]string{"PORT": "9000", "MAX_UPLOAD_BYTES": "100", "MAX_IMAGE_SIDE": "20", "MAX_IMAGE_PIXELS": "200", "WORKER_URL": "http://localhost:8001", "WORKER_TIMEOUT": "500ms", "MAX_IN_FLIGHT": "2", "ALLOWED_ORIGINS": "https://example.com, http://localhost:3000"}, Config{9000, 100, 20, 200, "http://localhost:8001", 500 * time.Millisecond, 2, []string{"https://example.com", "http://localhost:3000"}}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			clearEnvironment(t)
			for name, value := range test.environment {
				t.Setenv(name, value)
			}
			got, err := Load()
			if err != nil {
				t.Fatal(err)
			}
			if !reflect.DeepEqual(got, test.want) {
				t.Fatalf("settings = %+v, want %+v", got, test.want)
			}
		})
	}
}

func TestLoad_RejectsInvalidConfiguration(t *testing.T) {
	tests := []struct{ name, value string }{
		{"PORT", "0"}, {"PORT", "65536"}, {"PORT", "abc"},
		{"MAX_UPLOAD_BYTES", "0"}, {"MAX_UPLOAD_BYTES", "-1"}, {"MAX_UPLOAD_BYTES", "abc"},
		{"MAX_IMAGE_SIDE", "0"}, {"MAX_IMAGE_SIDE", "-1"}, {"MAX_IMAGE_SIDE", "abc"},
		{"MAX_IMAGE_PIXELS", "0"}, {"MAX_IMAGE_PIXELS", "-1"}, {"MAX_IMAGE_PIXELS", "abc"},
		{"MAX_IN_FLIGHT", "0"}, {"MAX_IN_FLIGHT", "-1"}, {"MAX_IN_FLIGHT", "abc"},
		{"WORKER_TIMEOUT", "0s"}, {"WORKER_TIMEOUT", "-1s"}, {"WORKER_TIMEOUT", "20"},
		{"WORKER_URL", "://bad"}, {"WORKER_URL", "worker:8000"}, {"WORKER_URL", "//worker:8000"}, {"WORKER_URL", "http://"}, {"WORKER_URL", "http://:8000"},
		{"ALLOWED_ORIGINS", "*"}, {"ALLOWED_ORIGINS", "example.com"}, {"ALLOWED_ORIGINS", "http://example.com/path"}, {"ALLOWED_ORIGINS", "http://example.com?query"}, {"ALLOWED_ORIGINS", "http://example.com#fragment"}, {"ALLOWED_ORIGINS", "http://user@example.com"}, {"ALLOWED_ORIGINS", "http://example.com:bad"}, {"ALLOWED_ORIGINS", "http://example.com,"},
	}
	for _, test := range tests {
		t.Run(test.name+"="+test.value, func(t *testing.T) {
			clearEnvironment(t)
			t.Setenv(test.name, test.value)
			_, err := Load()
			if err == nil || !strings.Contains(err.Error(), test.name) {
				t.Fatalf("error = %v, want variable %s", err, test.name)
			}
		})
	}
}

func clearEnvironment(t *testing.T) {
	t.Helper()
	for _, name := range []string{"PORT", "MAX_UPLOAD_BYTES", "MAX_IMAGE_SIDE", "MAX_IMAGE_PIXELS", "WORKER_URL", "WORKER_TIMEOUT", "MAX_IN_FLIGHT", "ALLOWED_ORIGINS"} {
		previous, exists := os.LookupEnv(name)
		t.Cleanup(func() {
			var err error
			if exists {
				err = os.Setenv(name, previous)
			} else {
				err = os.Unsetenv(name)
			}
			if err != nil {
				t.Error(err)
			}
		})
		if err := os.Unsetenv(name); err != nil {
			t.Fatal(err)
		}
	}
}
