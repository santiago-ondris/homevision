package httpapi

import (
	"context"
	"crypto/rand"
	"io"
	"net/http"
	"regexp"
	"runtime/debug"
	"slices"
	"time"

	"github.com/santiago-ondris/homevision/api/internal/requestid"
)

const (
	requestIDPattern = `^[A-Za-z0-9_-]{1,64}$`
	// nginx's status for a client that closed the connection; HTTP defines none.
	clientClosedStatus = 499
)

type observationKey struct{}

type responseObservation struct {
	http.ResponseWriter
	status   int
	bytesOut int64
	bytesIn  int64
	started  time.Time
	details  []any
	written  bool
}

func (record *responseObservation) WriteHeader(status int) {
	if record.written {
		return
	}
	record.status = status
	record.written = true
	record.ResponseWriter.WriteHeader(status)
}

func (record *responseObservation) Write(data []byte) (int, error) {
	if !record.written {
		record.WriteHeader(http.StatusOK)
	}
	count, err := record.ResponseWriter.Write(data)
	record.bytesOut += int64(count)
	return count, err
}

type countingBody struct {
	io.ReadCloser
	record *responseObservation
}

func (body *countingBody) Read(data []byte) (int, error) {
	count, err := body.ReadCloser.Read(data)
	body.record.bytesIn += int64(count)
	return count, err
}

func observation(req *http.Request) *responseObservation {
	return req.Context().Value(observationKey{}).(*responseObservation)
}

func (server *api) requestID(next http.Handler) http.Handler {
	valid := regexp.MustCompile(requestIDPattern)
	return http.HandlerFunc(func(resp http.ResponseWriter, req *http.Request) {
		id := req.Header.Get("X-Request-Id")
		if !valid.MatchString(id) {
			id = rand.Text()
		}
		resp.Header().Set("X-Request-Id", id)
		record := &responseObservation{ResponseWriter: resp, status: http.StatusOK}
		ctx := context.WithValue(requestid.WithRequestID(req.Context(), id), observationKey{}, record)
		next.ServeHTTP(record, req.WithContext(ctx))
	})
}

func (server *api) recoverPanic(next http.Handler) http.Handler {
	return http.HandlerFunc(func(resp http.ResponseWriter, req *http.Request) {
		defer func() {
			if failure := recover(); failure != nil {
				server.logger.Error(
					"request panicked",
					"request_id",
					requestid.RequestID(req.Context()),
					"error",
					failure,
					"stack",
					string(debug.Stack()),
				)
				server.writeError(resp, req, &routeError{
					status:  http.StatusInternalServerError,
					code:    "internal_error",
					message: "Something went wrong. Try again.",
				})
				// Recovery runs after the inner middleware unwinds, so log the completed error response here.
				server.logAccess(req)
			}
		}()
		next.ServeHTTP(resp, req)
	})
}

func (server *api) accessLog(next http.Handler) http.Handler {
	return http.HandlerFunc(func(resp http.ResponseWriter, req *http.Request) {
		record := observation(req)
		record.started = time.Now()
		req.Body = &countingBody{req.Body, record}
		next.ServeHTTP(resp, req)
		server.logAccess(req)
	})
}

func (server *api) logAccess(req *http.Request) {
	// TODO(prod): add metrics and tracing to track latency and failures across API and worker calls.
	record := observation(req)
	if req.Context().Err() != nil {
		record.status = clientClosedStatus
	}
	attributes := []any{
		"request_id", requestid.RequestID(req.Context()),
		"method", req.Method,
		"path", req.URL.Path,
		"status", record.status,
		"duration_ms", milliseconds(time.Since(record.started)),
		"bytes_in", record.bytesIn,
		"bytes_out", record.bytesOut,
	}
	attributes = append(attributes, record.details...)
	server.logger.Info("request completed", attributes...)
}

func (server *api) cors(next http.Handler) http.Handler {
	return http.HandlerFunc(func(resp http.ResponseWriter, req *http.Request) {
		resp.Header().Add("Vary", "Origin")
		origin := req.Header.Get("Origin")
		if slices.Contains(server.settings.AllowedOrigins, origin) {
			resp.Header().Set("Access-Control-Allow-Origin", origin)
			resp.Header().Set("Access-Control-Expose-Headers", "X-Request-Id, Server-Timing")
			if req.Method == http.MethodOptions && req.URL.Path == "/detect" {
				resp.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
				resp.Header().Set("Access-Control-Allow-Headers", "Content-Type, X-Request-Id")
			}
		}
		next.ServeHTTP(resp, req)
	})
}
