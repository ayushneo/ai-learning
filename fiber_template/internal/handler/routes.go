// Register aggregates every resource's routes into one call from
// cmd/api/main.go. Adding a resource means one block here, not touching
// main.go again -- same shape as fastapi_template's api/v1/router.py.
package handler

import "github.com/gofiber/fiber/v3"

func (h *Handler) Register(app *fiber.App) {
	v1 := app.Group("/v1")

	items := v1.Group("/items")
	items.Post("/", h.CreateItem)
	items.Get("/:id", h.GetItem)
	items.Get("/", h.ListItems)
	items.Delete("/:id", h.DeleteItem)
}
