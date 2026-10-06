package detector

import (
	"context"
	"errors"
	"net"
	"net/http"
	"syscall"
	"testing"
	"time"

	"github.com/santiago-ondris/homevision/api/internal/upload"
)

type failingTransport struct {
	err   error
	calls int
}

func (transport *failingTransport) RoundTrip(*http.Request) (*http.Response, error) {
	transport.calls++
	return nil, transport.err
}

func TestDetect_ReportsTransportFailuresWithoutRetrying(t *testing.T) {
	tests := []struct {
		name    string
		failure error
	}{
		{"DNS failure", &net.DNSError{Err: "no such host", Name: "worker.invalid", IsNotFound: true}},
		{"connection reset", syscall.ECONNRESET},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			transport := &failingTransport{err: test.failure}
			client := New("http://worker.invalid", time.Second)
			client.httpClient.Transport = transport
			_, err := client.Detect(context.Background(), upload.Image{})
			if !errors.Is(err, ErrUnavailable) || transport.calls != 1 {
				t.Fatalf("error = %v, attempts = %d", err, transport.calls)
			}
		})
	}
}
