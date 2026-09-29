// Item handlers. Plain functions holding a *service.ItemService field, not
// per-route dependency injection -- Fiber has no Depends() equivalent, so
// the constructed service is closed over once in cmd/api/main.go and shared
// across methods via the Handler struct. Same sharing fastapi_template gets
// from Depends(get_item_service), just a different mechanism, since the
// framework doesn't provide one.
package handler

import (
	"time"

	"github.com/go-playground/validator/v10"
	"github.com/gofiber/fiber/v3"
	"github.com/google/uuid"

	"fiber-template/internal/models"
	"fiber-template/internal/service"
)

type Handler struct {
	items    *service.ItemService
	validate *validator.Validate
}

func New(items *service.ItemService) *Handler {
	return &Handler{items: items, validate: newValidator()}
}

// Request/response DTOs, kept separate from models.Item (DB shape) -- the
// DB row and the API contract change for different reasons and at
// different times. Same split fastapi_template makes between models/ and
// schemas/.
type createItemRequest struct {
	Name        string  `json:"name" validate:"required"`
	Description *string `json:"description"`
}

type itemResponse struct {
	ID          uuid.UUID `json:"id"`
	Name        string    `json:"name"`
	Description *string   `json:"description"`
	CreatedAt   time.Time `json:"created_at"`
}

func toItemResponse(m *models.Item) itemResponse {
	return itemResponse{ID: m.ID, Name: m.Name, Description: m.Description, CreatedAt: m.CreatedAt}
}

func (h *Handler) CreateItem(c fiber.Ctx) error {
	var req createItemRequest
	if err := c.Bind().Body(&req); err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "invalid request body")
	}
	if err := h.validate.Struct(req); err != nil {
		return fiber.NewError(fiber.StatusUnprocessableEntity, err.Error())
	}
	item, err := h.items.Create(service.CreateItemInput{Name: req.Name, Description: req.Description})
	if err != nil {
		return err
	}
	return c.Status(fiber.StatusCreated).JSON(toItemResponse(item))
}

func (h *Handler) GetItem(c fiber.Ctx) error {
	id, err := uuid.Parse(c.Params("id"))
	if err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "invalid item id")
	}
	item, err := h.items.Get(id)
	if err != nil {
		return err
	}
	return c.JSON(toItemResponse(item))
}

func (h *Handler) ListItems(c fiber.Ctx) error {
	limit := fiber.Query(c, "limit", 50)
	offset := fiber.Query(c, "offset", 0)
	items, err := h.items.List(limit, offset)
	if err != nil {
		return err
	}
	out := make([]itemResponse, len(items))
	for i, item := range items {
		out[i] = toItemResponse(&item)
	}
	return c.JSON(out)
}

func (h *Handler) DeleteItem(c fiber.Ctx) error {
	id, err := uuid.Parse(c.Params("id"))
	if err != nil {
		return fiber.NewError(fiber.StatusBadRequest, "invalid item id")
	}
	if err := h.items.Delete(id); err != nil {
		return err
	}
	return c.SendStatus(fiber.StatusNoContent)
}
