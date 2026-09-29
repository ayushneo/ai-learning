// Package apperror mirrors fastapi_template's core/exceptions.py: a small
// typed error + one handler at the edge (wired in cmd/api/main.go's
// fiber.Config.ErrorHandler) instead of every service/repository importing
// Fiber to pick an HTTP status. Worth it past ~2-3 resources; for a single
// endpoint, returning fiber.NewError(404, ...) directly is the more honest
// lazy choice -- see fastapi_template's own README, same call, same reasoning.
package apperror

import "net/http"

type AppError struct {
	Code    int
	Message string
}

func (e *AppError) Error() string { return e.Message }

func NotFound(msg string) *AppError {
	return &AppError{Code: http.StatusNotFound, Message: msg}
}

func Conflict(msg string) *AppError {
	return &AppError{Code: http.StatusConflict, Message: msg}
}
