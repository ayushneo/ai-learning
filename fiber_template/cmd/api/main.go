// App factory + wiring + graceful shutdown. Run with `go run ./cmd/api` in
// dev, or the compiled binary in prod -- see Makefile.
package main

import (
	"errors"
	"log/slog"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"

	"github.com/gofiber/fiber/v3"
	"github.com/gofiber/fiber/v3/middleware/cors"
	"github.com/gofiber/fiber/v3/middleware/logger"
	"github.com/gofiber/fiber/v3/middleware/recover"
	"github.com/gofiber/fiber/v3/middleware/requestid"

	"fiber-template/internal/apperror"
	"fiber-template/internal/config"
	"fiber-template/internal/db"
	"fiber-template/internal/handler"
	"fiber-template/internal/repository"
	"fiber-template/internal/service"
)

func main() {
	cfg := config.Load()

	gormDB, err := db.Open(cfg.DatabaseURL)
	if err != nil {
		slog.Error("db connect failed", "err", err)
		os.Exit(1)
	}

	items := service.NewItemService(repository.NewItemRepository(gormDB))
	h := handler.New(items)

	app := fiber.New(fiber.Config{
		// One error handler for the whole app -- *apperror.AppError carries
		// its own status code, anything else is an unhandled 500. Direct
		// equivalent of fastapi_template's app_error_handler, registered the
		// same way (once, at the edge) but via Fiber's own Config field
		// instead of add_exception_handler -- the framework's native hook
		// for this, so no middleware needed to get it.
		ErrorHandler: func(c fiber.Ctx, err error) error {
			if appErr, ok := err.(*apperror.AppError); ok {
				return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
			}
			if fiberErr, ok := err.(*fiber.Error); ok {
				return c.Status(fiberErr.Code).JSON(fiber.Map{"detail": fiberErr.Message})
			}
			slog.Error("unhandled error", "err", err)
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"detail": "internal server error"})
		},
	})

	// requestid/recover/logger ship in Fiber core -- unlike
	// fastapi_template's hand-rolled request_id.py (Starlette has no
	// built-in), there's nothing to write here, just wire what's already in
	// the framework.
	app.Use(requestid.New())
	app.Use(recover.New())
	app.Use(logger.New())
	if origins := os.Getenv("CORS_ORIGINS"); origins != "" {
		app.Use(cors.New(cors.Config{AllowOrigins: []string{origins}}))
	}

	app.Get("/health", func(c fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok"})
	})

	h.Register(app)

	// Listen from a goroutine so the signal wait below can block the main
	// one -- same shape as gofiber/recipes' graceful-shutdown recipe.
	go func() {
		if err := app.Listen(":" + cfg.Port); err != nil && !errors.Is(err, net.ErrClosed) {
			slog.Error("listen failed", "err", err)
			os.Exit(1)
		}
	}()

	quit := make(chan os.Signal, 1)
	signal.Notify(quit, os.Interrupt, syscall.SIGTERM)
	<-quit

	slog.Info("shutting down")
	if err := app.ShutdownWithTimeout(5 * time.Second); err != nil {
		slog.Error("shutdown error", "err", err)
	}
	if sqlDB, err := gormDB.DB(); err == nil {
		sqlDB.Close()
	}
}
