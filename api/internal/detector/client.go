// Package detector calls the private image detection service.
package detector

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/santiago-ondris/homevision/api/internal/requestid"
	"github.com/santiago-ondris/homevision/api/internal/upload"
)

const (
	dialTimeout                = 5 * time.Second
	tlsHandshakeTimeout        = 5 * time.Second
	readinessTimeout           = 2 * time.Second
	maximumResponseBytes int64 = 5 << 20
)

// ErrTimeout reports an expired worker deadline.
var ErrTimeout = errors.New("detector timeout")

// ErrUnavailable reports an unreachable worker or an invalid response.
var ErrUnavailable = errors.New("detector unavailable")

// RejectedError carries a worker validation error.
type RejectedError struct {
	Status        int
	Code, Message string
}

func (err *RejectedError) Error() string { return err.Message }

// Dimensions describes the worker's decoded image.
type Dimensions struct {
	Width  int `json:"width"`
	Height int `json:"height"`
}

// Box holds a checkbox and its measured fill ratio.
type Box struct {
	BBox      [4]int
	IsChecked bool
	FillRatio float64
}

// Timings holds the worker's processing durations in milliseconds.
type Timings struct {
	Decode   float64 `json:"decode"`
	Detect   float64 `json:"detect"`
	Classify float64 `json:"classify"`
}

// Result holds the validated worker response.
type Result struct {
	Image   Dimensions
	Boxes   []Box
	Timings Timings
}

// Client reuses one HTTP client for worker calls.
type Client struct {
	baseURL    string
	httpClient *http.Client
}

// New builds a worker client with bounded connection and header waits.
func New(baseURL string, timeout time.Duration) *Client {
	transport := http.DefaultTransport.(*http.Transport).Clone()
	transport.DialContext = (&net.Dialer{Timeout: dialTimeout}).DialContext
	transport.TLSHandshakeTimeout = tlsHandshakeTimeout
	transport.ResponseHeaderTimeout = timeout
	return &Client{
		baseURL: strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{
			Transport: transport,
			CheckRedirect: func(*http.Request, []*http.Request) error {
				return http.ErrUseLastResponse
			},
		},
	}
}

// Detect submits raw image bytes and validates the entire worker response.
func (client *Client) Detect(ctx context.Context, picture upload.Image) (Result, error) {
	req, err := http.NewRequestWithContext(
		ctx,
		http.MethodPost,
		client.baseURL+"/v1/detect",
		bytes.NewReader(picture.Bytes),
	)
	if err != nil {
		return Result{}, fmt.Errorf("creating worker request: %w", ErrUnavailable)
	}
	req.Header.Set("Content-Type", picture.Format)
	req.Header.Set("X-Request-Id", requestid.RequestID(ctx))
	// TODO(prod): retry once on connection errors; the call is idempotent
	resp, err := client.httpClient.Do(req)
	if err != nil {
		return Result{}, callError(ctx, err)
	}
	data, err := readResponse(resp)
	if err != nil {
		return Result{}, callError(ctx, err)
	}
	if resp.StatusCode != http.StatusOK {
		return Result{}, rejection(resp.StatusCode, data)
	}
	result, err := decodeResult(data)
	if err != nil {
		return Result{}, fmt.Errorf("decoding worker response: %v: %w", err, ErrUnavailable)
	}
	return result, nil
}

// Ready checks worker health within two seconds.
func (client *Client) Ready(ctx context.Context) error {
	ctx, cancel := context.WithTimeout(ctx, readinessTimeout)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, client.baseURL+"/healthz", nil)
	if err != nil {
		return fmt.Errorf("creating worker health request: %w", ErrUnavailable)
	}
	req.Header.Set("X-Request-Id", requestid.RequestID(ctx))
	resp, err := client.httpClient.Do(req)
	if err != nil {
		return callError(ctx, err)
	}
	_, err = readResponse(resp)
	if err != nil {
		return callError(ctx, err)
	}
	if resp.StatusCode != http.StatusOK {
		return ErrUnavailable
	}
	return nil
}

func readResponse(resp *http.Response) ([]byte, error) {
	data, readError := io.ReadAll(io.LimitReader(resp.Body, maximumResponseBytes+1))
	closeError := resp.Body.Close()
	if readError != nil {
		return nil, fmt.Errorf("reading worker response: %w", readError)
	}
	if closeError != nil {
		return nil, fmt.Errorf("closing worker response: %w", closeError)
	}
	if int64(len(data)) > maximumResponseBytes {
		return nil, fmt.Errorf("worker response exceeds byte limit: %w", ErrUnavailable)
	}
	return data, nil
}

func callError(ctx context.Context, err error) error {
	if errors.Is(ctx.Err(), context.Canceled) {
		return context.Canceled
	}
	if errors.Is(ctx.Err(), context.DeadlineExceeded) || errors.Is(err, context.DeadlineExceeded) {
		return ErrTimeout
	}
	return fmt.Errorf("calling worker: %v: %w", err, ErrUnavailable)
}

func rejection(status int, data []byte) error {
	expected := map[int]string{
		http.StatusRequestEntityTooLarge: "file_too_large",
		http.StatusUnsupportedMediaType:  "unsupported_media_type",
		http.StatusUnprocessableEntity:   "invalid_image",
	}
	code, accepted := expected[status]
	if !accepted {
		return ErrUnavailable
	}
	var body struct {
		Error struct {
			Code    string `json:"code"`
			Message string `json:"message"`
		} `json:"error"`
	}
	if err := decodeStrict(data, &body); err != nil {
		return fmt.Errorf("decoding worker error: %v: %w", err, ErrUnavailable)
	}
	if body.Error.Code != code || body.Error.Message == "" {
		return ErrUnavailable
	}
	return &RejectedError{
		Status:  status,
		Code:    body.Error.Code,
		Message: body.Error.Message,
	}
}

func decodeStrict(data []byte, target any) error {
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(target); err != nil {
		return fmt.Errorf("decoding JSON: %w", err)
	}
	var trailing any
	if err := decoder.Decode(&trailing); !errors.Is(err, io.EOF) {
		return errors.New("response must contain one JSON value")
	}
	return nil
}
