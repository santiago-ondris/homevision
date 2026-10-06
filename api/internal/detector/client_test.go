package detector

import (
	"bytes"
	"context"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"github.com/santiago-ondris/homevision/api/internal/requestid"
	"github.com/santiago-ondris/homevision/api/internal/upload"
)

const validResult = `{"image":{"width":10,"height":20},"boxes":[{"bbox":[1,2,4,5],"is_checked":true,"fill_ratio":0.2}],"timings_ms":{"decode":1,"detect":2,"classify":3}}`

type workerResponseCase struct {
	name      string
	status    int
	body      string
	wantError error
	rejected  string
}

func TestDetect_ValidatesWorkerResponses(t *testing.T) {
	tests := []workerResponseCase{
		{"success", 200, validResult, nil, ""},
		{"empty result", 200, strings.Replace(validResult, `[{"bbox":[1,2,4,5],"is_checked":true,"fill_ratio":0.2}]`, `[]`, 1), nil, ""},
		{"size rejection", 413, `{"error":{"code":"file_too_large","message":"Too large."}}`, nil, "file_too_large"},
		{"format rejection", 415, `{"error":{"code":"unsupported_media_type","message":"Send PNG or JPEG."}}`, nil, "unsupported_media_type"},
		{"image rejection", 422, `{"error":{"code":"invalid_image","message":"Cannot decode image."}}`, nil, "invalid_image"},
		{"server error", 500, `{}`, ErrUnavailable, ""},
		{"other status", 400, `{}`, ErrUnavailable, ""},
		{"redirect", 302, `{}`, ErrUnavailable, ""},
		{"unknown field", 200, strings.Replace(validResult, `"width":10`, `"extra":1,"width":10`, 1), ErrUnavailable, ""},
		{"three coordinates", 200, strings.Replace(validResult, `[1,2,4,5]`, `[1,2,4]`, 1), ErrUnavailable, ""},
		{"outside image", 200, strings.Replace(validResult, `[1,2,4,5]`, `[1,2,11,5]`, 1), ErrUnavailable, ""},
		{"negative coordinate", 200, strings.Replace(validResult, `[1,2,4,5]`, `[-1,2,4,5]`, 1), ErrUnavailable, ""},
		{"zero width box", 200, strings.Replace(validResult, `[1,2,4,5]`, `[4,2,4,5]`, 1), ErrUnavailable, ""},
		{"missing boolean", 200, strings.Replace(validResult, `"is_checked":true,`, ``, 1), ErrUnavailable, ""},
		{"missing boxes", 200, `{"image":{"width":10,"height":20},"timings_ms":{"decode":1,"detect":2,"classify":3}}`, ErrUnavailable, ""},
		{"null boxes", 200, strings.Replace(validResult, `[{"bbox":[1,2,4,5],"is_checked":true,"fill_ratio":0.2}]`, `null`, 1), ErrUnavailable, ""},
		{"missing timings", 200, `{"image":{"width":10,"height":20},"boxes":[]}`, ErrUnavailable, ""},
		{"trailing JSON", 200, validResult + `{}`, ErrUnavailable, ""},
		{"malformed JSON", 200, `{`, ErrUnavailable, ""},
		{"over response cap", 200, strings.Repeat(" ", int(maximumResponseBytes)) + validResult, ErrUnavailable, ""},
		{"bad rejection", 422, `{"error":{"code":"internal_error","message":"Wrong code."}}`, ErrUnavailable, ""},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			runWorkerResponseCase(t, test)
		})
	}
}

func runWorkerResponseCase(t *testing.T, test workerResponseCase) {
	worker := httptest.NewServer(http.HandlerFunc(func(resp http.ResponseWriter, req *http.Request) {
		data, err := io.ReadAll(req.Body)
		if err != nil {
			t.Error(err)
		}
		if req.Method != http.MethodPost || req.URL.Path != "/v1/detect" || req.Header.Get("Content-Type") != "image/png" || req.Header.Get("X-Request-Id") != "request_1" || !bytes.Equal(data, []byte("image")) {
			t.Errorf("unexpected worker request: %v, body %q", req, data)
		}
		resp.WriteHeader(test.status)
		if _, err := io.WriteString(resp, test.body); err != nil {
			t.Error(err)
		}
	}))
	defer worker.Close()
	result, err := New(worker.URL, time.Second).Detect(requestid.WithRequestID(context.Background(), "request_1"), upload.Image{Bytes: []byte("image"), Format: "image/png"})
	test.assertResult(t, result, err)
}

func (test workerResponseCase) assertResult(t *testing.T, result Result, err error) {
	if test.rejected != "" {
		var rejected *RejectedError
		if !errors.As(err, &rejected) || rejected.Status != test.status || rejected.Code != test.rejected || rejected.Message == "" {
			t.Fatalf("error = %v", err)
		}
		return
	}
	if test.wantError != nil {
		if !errors.Is(err, test.wantError) {
			t.Fatalf("error = %v, want %v", err, test.wantError)
		}
		return
	}
	if err != nil {
		t.Fatal(err)
	}
	if result.Image != (Dimensions{10, 20}) || result.Timings != (Timings{1, 2, 3}) {
		t.Fatalf("result = %+v", result)
	}
	if test.name == "success" && (len(result.Boxes) != 1 || result.Boxes[0] != (Box{[4]int{1, 2, 4, 5}, true, 0.2})) {
		t.Fatalf("boxes = %+v", result.Boxes)
	}
	if test.name == "empty result" && len(result.Boxes) != 0 {
		t.Fatalf("boxes = %+v", result.Boxes)
	}
}

func TestDetect_MapsContextAndConnectionFailures(t *testing.T) {
	worker := httptest.NewServer(http.HandlerFunc(func(http.ResponseWriter, *http.Request) {}))
	worker.Close()
	cancelled, cancel := context.WithCancel(context.Background())
	cancel()
	expired, expire := context.WithDeadline(context.Background(), time.Time{})
	defer expire()
	tests := []struct {
		name string
		ctx  context.Context
		want error
	}{
		{"connection refused", context.Background(), ErrUnavailable},
		{"caller cancelled", cancelled, context.Canceled},
		{"deadline exceeded", expired, ErrTimeout},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			_, err := New(worker.URL, time.Second).Detect(test.ctx, upload.Image{})
			if !errors.Is(err, test.want) {
				t.Fatalf("error = %v, want %v", err, test.want)
			}
		})
	}
}

func TestReady_ChecksHealthAndForwardsIdentifier(t *testing.T) {
	tests := []struct {
		name      string
		status    int
		cancelled bool
		want      error
	}{
		{"healthy", 200, false, nil}, {"unhealthy", 500, false, ErrUnavailable}, {"cancelled", 200, true, context.Canceled},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			worker := httptest.NewServer(http.HandlerFunc(func(resp http.ResponseWriter, req *http.Request) {
				if req.URL.Path != "/healthz" || req.Method != http.MethodGet || req.Header.Get("X-Request-Id") != "ready_1" {
					t.Errorf("unexpected health request: %v", req)
				}
				resp.WriteHeader(test.status)
			}))
			defer worker.Close()
			ctx, cancel := context.WithCancel(requestid.WithRequestID(context.Background(), "ready_1"))
			defer cancel()
			if test.cancelled {
				cancel()
			}
			err := New(worker.URL, time.Second).Ready(ctx)
			if !errors.Is(err, test.want) {
				t.Fatalf("error = %v, want %v", err, test.want)
			}
		})
	}
}
