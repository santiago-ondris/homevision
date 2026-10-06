package httpapi

import (
	"encoding/json"
	"errors"
	"fmt"
	"net/http"

	"github.com/santiago-ondris/homevision/api/internal/detector"
	"github.com/santiago-ondris/homevision/api/internal/requestid"
	"github.com/santiago-ondris/homevision/api/internal/upload"
)

const bytesPerMegabyte = 1 << 20

type routeError struct {
	status        int
	code, message string
}

func (err *routeError) Error() string { return err.message }

type overloadedError struct{}

func (*overloadedError) Error() string { return "all detection slots are occupied" }

type errorDetail struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}
type errorResponse struct {
	Error errorDetail `json:"error"`
}

func mapError(err error) (int, errorDetail) {
	var invalidRequest *upload.InvalidRequestError
	var tooLarge *upload.TooLargeError
	var unsupported *upload.UnsupportedFormatError
	var invalidImage *upload.InvalidImageError
	var side *upload.SideLimitError
	var pixels *upload.PixelLimitError
	var rejected *detector.RejectedError
	var route *routeError
	var overloaded *overloadedError
	switch {
	case errors.As(err, &invalidRequest):
		return http.StatusBadRequest, errorDetail{
			Code:    "invalid_request",
			Message: invalidRequest.Reason,
		}
	case errors.As(err, &tooLarge):
		return http.StatusRequestEntityTooLarge, errorDetail{
			Code: "file_too_large",
			Message: fmt.Sprintf(
				"The file is larger than the %g MB limit.",
				float64(tooLarge.Limit)/bytesPerMegabyte,
			),
		}
	case errors.As(err, &unsupported):
		return http.StatusUnsupportedMediaType, errorDetail{
			Code:    "unsupported_media_type",
			Message: "Send a PNG or JPEG image.",
		}
	case errors.As(err, &invalidImage):
		return http.StatusUnprocessableEntity, errorDetail{
			Code:    "invalid_image",
			Message: "The image header could not be read. Send a valid PNG or JPEG image.",
		}
	case errors.As(err, &side):
		return http.StatusUnprocessableEntity, errorDetail{
			Code: "invalid_image",
			Message: fmt.Sprintf(
				"The image is %d × %d px. The limit is %d px per side.",
				side.Width,
				side.Height,
				side.Limit,
			),
		}
	case errors.As(err, &pixels):
		return http.StatusUnprocessableEntity, errorDetail{
			Code: "invalid_image",
			Message: fmt.Sprintf(
				"The image is %d × %d px (%d pixels). The limit is %d pixels.",
				pixels.Width,
				pixels.Height,
				pixels.Actual,
				pixels.Limit,
			),
		}
	case errors.As(err, &rejected):
		return rejected.Status, errorDetail{
			Code:    rejected.Code,
			Message: rejected.Message,
		}
	case errors.As(err, &route):
		return route.status, errorDetail{
			Code:    route.code,
			Message: route.message,
		}
	case errors.As(err, &overloaded):
		return http.StatusServiceUnavailable, errorDetail{
			Code:    "overloaded",
			Message: "The service is busy. Try again in one second.",
		}
	case errors.Is(err, detector.ErrTimeout):
		return http.StatusGatewayTimeout, errorDetail{
			Code:    "detector_timeout",
			Message: "Image processing took too long. Try again.",
		}
	case errors.Is(err, detector.ErrUnavailable):
		return http.StatusServiceUnavailable, errorDetail{
			Code:    "detector_unavailable",
			Message: "Image processing is unavailable. Try again shortly.",
		}
	default:
		return http.StatusInternalServerError, errorDetail{
			Code:    "internal_error",
			Message: "Something went wrong. Try again.",
		}
	}
}

func (server *api) writeError(resp http.ResponseWriter, req *http.Request, err error) {
	if req.Context().Err() != nil {
		observation(req).status = clientClosedStatus
		return
	}
	status, detail := mapError(err)
	if status == http.StatusInternalServerError {
		server.logger.Error("request failed", "request_id", requestid.RequestID(req.Context()), "error", err)
	}
	server.writeJSON(resp, req, status, errorResponse{detail})
}

func (server *api) writeJSON(resp http.ResponseWriter, req *http.Request, status int, body any) {
	if req.Context().Err() != nil {
		observation(req).status = clientClosedStatus
		return
	}
	data, err := json.Marshal(body)
	if err != nil {
		server.writeError(resp, req, fmt.Errorf("encoding response: %w", err))
		return
	}
	resp.Header().Set("Content-Type", "application/json")
	resp.WriteHeader(status)
	if _, err := resp.Write(data); err != nil {
		server.logger.Error("writing response", "request_id", requestid.RequestID(req.Context()), "error", err)
	}
}
