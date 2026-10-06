// Package requestid stores request identifiers in a context.
package requestid

import "context"

type requestIDKey struct{}

// WithRequestID attaches the identifier to the context.
func WithRequestID(ctx context.Context, id string) context.Context {
	return context.WithValue(ctx, requestIDKey{}, id)
}

// RequestID returns the identifier attached to the context.
func RequestID(ctx context.Context) string {
	id, _ := ctx.Value(requestIDKey{}).(string)
	return id
}
