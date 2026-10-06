package upload

import (
	"bytes"
	"errors"
	"image"
	"image/jpeg"
	"image/png"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"reflect"
	"testing"
)

func TestRead_ValidatesUploadInContractOrder(t *testing.T) {
	pngBytes := encodeImage(t, "png", 3, 2)
	jpegBytes := encodeImage(t, "jpeg", 3, 2)
	tests := []struct {
		name      string
		files     [][]byte
		filename  string
		fields    bool
		limits    Limits
		errorType error
		format    string
	}{
		{name: "PNG", files: [][]byte{pngBytes}, format: "image/png"},
		{name: "JPEG", files: [][]byte{jpegBytes}, format: "image/jpeg"},
		{name: "JPEG named PNG", files: [][]byte{jpegBytes}, filename: "image.png", format: "image/jpeg"},
		{name: "ignored form fields", files: [][]byte{pngBytes}, fields: true, format: "image/png"},
		{name: "exact byte limit", files: [][]byte{pngBytes}, limits: Limits{int64(len(pngBytes)), 10, 100}, format: "image/png"},
		{name: "one byte over", files: [][]byte{pngBytes}, limits: Limits{int64(len(pngBytes) - 1), 10, 100}, errorType: &TooLargeError{}},
		{name: "text named PNG", files: [][]byte{[]byte("text")}, filename: "image.png", errorType: &UnsupportedFormatError{}},
		{name: "no file", errorType: &InvalidRequestError{}},
		{name: "empty file", files: [][]byte{{}}, errorType: &InvalidRequestError{}},
		{name: "two files", files: [][]byte{pngBytes, pngBytes}, errorType: &InvalidRequestError{}},
		{name: "structure before format", files: [][]byte{[]byte("text"), pngBytes}, errorType: &InvalidRequestError{}},
		{name: "structure before size", files: [][]byte{pngBytes, pngBytes}, limits: Limits{1, 10, 100}, errorType: &InvalidRequestError{}},
		{name: "unreadable PNG header", files: [][]byte{{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a}}, errorType: &InvalidImageError{}},
		{name: "unreadable JPEG header", files: [][]byte{{0xff, 0xd8, 0xff}}, errorType: &InvalidImageError{}},
		{name: "width over limit", files: [][]byte{pngBytes}, limits: Limits{1024, 2, 100}, errorType: &SideLimitError{}},
		{name: "height over limit", files: [][]byte{encodeImage(t, "png", 2, 3)}, limits: Limits{1024, 2, 100}, errorType: &SideLimitError{}},
		{name: "pixel count over limit", files: [][]byte{pngBytes}, limits: Limits{1024, 10, 5}, errorType: &PixelLimitError{}},
		{name: "dimensions at limits", files: [][]byte{pngBytes}, limits: Limits{1024, 3, 6}, format: "image/png"},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			limits := test.limits
			if limits.MaxBytes == 0 {
				limits = Limits{1024, 10, 100}
			}
			req := multipartRequest(t, test.files, test.filename, test.fields)
			got, err := Read(httptest.NewRecorder(), req, limits)
			if test.errorType != nil {
				if reflect.TypeOf(err) != reflect.TypeOf(test.errorType) {
					t.Fatalf("error = %v (%T), want %T", err, err, test.errorType)
				}
				var oversized *TooLargeError
				if errors.As(err, &oversized) && oversized.Limit != limits.MaxBytes {
					t.Fatalf("size error = %+v", oversized)
				}
				return
			}
			if err != nil {
				t.Fatal(err)
			}
			if got.Format != test.format || got.Width != 3 || got.Height != 2 || !bytes.Equal(got.Bytes, test.files[0]) {
				t.Fatalf("image = %+v", got)
			}
		})
	}
}

func TestRead_RejectsMalformedAndOversizedBodies(t *testing.T) {
	tests := []struct {
		name, contentType string
		body              []byte
		errorType         error
	}{
		{"not multipart", "text/plain", []byte("text"), &InvalidRequestError{}},
		{"missing boundary", "multipart/form-data", []byte("text"), &InvalidRequestError{}},
		{"malformed multipart", "multipart/form-data; boundary=test", []byte("--test\r\ninvalid"), &InvalidRequestError{}},
		{"body cutoff", "multipart/form-data; boundary=test", append([]byte("--test\r\nContent-Disposition: form-data; name=\"file\"; filename=\"image.png\"\r\n\r\n"), bytes.Repeat([]byte("x"), int(multipartAllowance)+100)...), &TooLargeError{}},
	}
	for _, test := range tests {
		t.Run(test.name, func(t *testing.T) {
			req := httptest.NewRequest(http.MethodPost, "/detect", bytes.NewReader(test.body))
			req.Header.Set("Content-Type", test.contentType)
			_, err := Read(httptest.NewRecorder(), req, Limits{10, 10, 100})
			if reflect.TypeOf(err) != reflect.TypeOf(test.errorType) {
				t.Fatalf("error = %v (%T), want %T", err, err, test.errorType)
			}
		})
	}
}

func encodeImage(t *testing.T, format string, width, height int) []byte {
	t.Helper()
	var buffer bytes.Buffer
	picture := image.NewRGBA(image.Rect(0, 0, width, height))
	var err error
	if format == "png" {
		err = png.Encode(&buffer, picture)
	} else {
		err = jpeg.Encode(&buffer, picture, nil)
	}
	if err != nil {
		t.Fatal(err)
	}
	return buffer.Bytes()
}

func multipartRequest(t *testing.T, files [][]byte, filename string, fields bool) *http.Request {
	t.Helper()
	var buffer bytes.Buffer
	writer := multipart.NewWriter(&buffer)
	if fields {
		if err := writer.WriteField("description", "ignored"); err != nil {
			t.Fatal(err)
		}
	}
	for _, data := range files {
		part, err := writer.CreateFormFile("file", filename)
		if err != nil {
			t.Fatal(err)
		}
		if _, err = part.Write(data); err != nil {
			t.Fatal(err)
		}
	}
	if err := writer.Close(); err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/detect", &buffer)
	req.Header.Set("Content-Type", writer.FormDataContentType())
	return req
}
