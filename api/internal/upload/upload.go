// Package upload validates document images without writing uploads to disk.
package upload

import (
	"bytes"
	"errors"
	"fmt"
	"image"
	_ "image/jpeg" // Register JPEG headers for image.DecodeConfig.
	_ "image/png"  // Register PNG headers for image.DecodeConfig.
	"io"
	"math"
	"net/http"
)

const multipartAllowance int64 = 1 << 20

// Limits bounds the uploaded bytes and header dimensions.
type Limits struct {
	MaxBytes  int64
	MaxSide   int
	MaxPixels int64
}

// Image holds the bytes and metadata read from the image header.
type Image struct {
	Bytes  []byte
	Format string
	Width  int
	Height int
}

// InvalidRequestError reports an invalid multipart upload.
type InvalidRequestError struct{ Reason string }

func (err *InvalidRequestError) Error() string { return err.Reason }

// TooLargeError reports a file exceeding the byte limit.
type TooLargeError struct{ Limit int64 }

func (err *TooLargeError) Error() string {
	return fmt.Sprintf("file exceeds the %d byte limit", err.Limit)
}

// UnsupportedFormatError reports bytes without a PNG or JPEG signature.
type UnsupportedFormatError struct{}

func (*UnsupportedFormatError) Error() string { return "unsupported image format" }

// InvalidImageError reports an unreadable image header.
type InvalidImageError struct{ Cause error }

func (err *InvalidImageError) Error() string {
	return fmt.Sprintf("reading image header: %v", err.Cause)
}
func (err *InvalidImageError) Unwrap() error { return err.Cause }

// SideLimitError reports dimensions exceeding the side limit.
type SideLimitError struct{ Width, Height, Limit int }

func (err *SideLimitError) Error() string {
	return fmt.Sprintf("image is %d x %d; side limit is %d", err.Width, err.Height, err.Limit)
}

// PixelLimitError reports dimensions exceeding the pixel limit.
type PixelLimitError struct {
	Width, Height int
	Actual, Limit int64
}

func (err *PixelLimitError) Error() string {
	return fmt.Sprintf("image has %d pixels; limit is %d", err.Actual, err.Limit)
}

// Read extracts one file and validates size, signature and header dimensions.
func Read(resp http.ResponseWriter, req *http.Request, limits Limits) (Image, error) {
	if err := req.Context().Err(); err != nil {
		return Image{}, err
	}
	req.Body = http.MaxBytesReader(resp, req.Body, addAllowance(limits.MaxBytes, multipartAllowance))
	data, err := readMultipart(req, limits.MaxBytes)
	if err != nil {
		return Image{}, err
	}
	if int64(len(data)) > limits.MaxBytes {
		return Image{}, &TooLargeError{limits.MaxBytes}
	}
	format := detectFormat(data)
	if format == "" {
		return Image{}, &UnsupportedFormatError{}
	}
	dimensions, _, err := image.DecodeConfig(bytes.NewReader(data))
	if err != nil {
		return Image{}, &InvalidImageError{err}
	}
	if dimensions.Width > limits.MaxSide || dimensions.Height > limits.MaxSide {
		return Image{}, &SideLimitError{
			Width:  dimensions.Width,
			Height: dimensions.Height,
			Limit:  limits.MaxSide,
		}
	}
	pixels := int64(dimensions.Width) * int64(dimensions.Height)
	if pixels > limits.MaxPixels {
		return Image{}, &PixelLimitError{
			Width:  dimensions.Width,
			Height: dimensions.Height,
			Actual: pixels,
			Limit:  limits.MaxPixels,
		}
	}
	return Image{
		Bytes:  data,
		Format: format,
		Width:  dimensions.Width,
		Height: dimensions.Height,
	}, nil
}

func readMultipart(req *http.Request, limit int64) ([]byte, error) {
	reader, err := req.MultipartReader()
	if err != nil {
		return nil, &InvalidRequestError{"Send the image as multipart/form-data in a part named \"file\"."}
	}
	var data []byte
	found := false
	for {
		if err := req.Context().Err(); err != nil {
			return nil, err
		}
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, multipartError(req, err, limit)
		}
		if part.FormName() != "file" {
			continue
		}
		if found {
			return nil, &InvalidRequestError{"Send exactly one part named \"file\"."}
		}
		found = true
		data, err = io.ReadAll(io.LimitReader(part, addAllowance(limit, 1)))
		if err != nil {
			return nil, multipartError(req, err, limit)
		}
	}
	if !found {
		return nil, &InvalidRequestError{"Send the image in a part named \"file\"."}
	}
	if len(data) == 0 {
		return nil, &InvalidRequestError{"The file is empty. Send a PNG or JPEG image."}
	}
	return data, nil
}

func multipartError(req *http.Request, err error, limit int64) error {
	if req.Context().Err() != nil {
		return req.Context().Err()
	}
	var oversized *http.MaxBytesError
	if errors.As(err, &oversized) {
		return &TooLargeError{limit}
	}
	return &InvalidRequestError{"The multipart upload is malformed. Send one file part named \"file\"."}
}

func detectFormat(data []byte) string {
	if bytes.HasPrefix(data, []byte{0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a}) {
		return "image/png"
	}
	if bytes.HasPrefix(data, []byte{0xff, 0xd8, 0xff}) {
		return "image/jpeg"
	}
	return ""
}

func addAllowance(limit, allowance int64) int64 {
	return min(limit, math.MaxInt64-allowance) + allowance
}
