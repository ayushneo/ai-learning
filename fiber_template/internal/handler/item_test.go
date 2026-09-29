// In-memory SQLite via GORM's sqlite driver, not a real Postgres -- fast, no
// docker-compose required to run `go test`. Same trade-off fastapi_template
// makes with aiosqlite: fine for this template's CRUD routes, point at a
// real Postgres test DB instead if you lean on Postgres-specific features.
//
// fiber.App.Test(req) is the framework's own in-process test helper (native
// feature, no httptest+real-listener needed) -- same "hit the app directly,
// no real socket" idea as fastapi_template's ASGITransport, different
// mechanism because the framework provides it directly here.
package handler

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/gofiber/fiber/v3"
	"github.com/stretchr/testify/require"
	"gorm.io/driver/sqlite"
	"gorm.io/gorm"

	"fiber-template/internal/apperror"
	"fiber-template/internal/models"
	"fiber-template/internal/repository"
	"fiber-template/internal/service"
)

func newTestApp(t *testing.T) *fiber.App {
	t.Helper()
	gormDB, err := gorm.Open(sqlite.Open(":memory:"), &gorm.Config{})
	require.NoError(t, err)
	require.NoError(t, gormDB.AutoMigrate(&models.Item{}))

	h := New(service.NewItemService(repository.NewItemRepository(gormDB)))

	app := fiber.New(fiber.Config{
		ErrorHandler: func(c fiber.Ctx, err error) error {
			if appErr, ok := err.(*apperror.AppError); ok {
				return c.Status(appErr.Code).JSON(fiber.Map{"detail": appErr.Message})
			}
			if fiberErr, ok := err.(*fiber.Error); ok {
				return c.Status(fiberErr.Code).JSON(fiber.Map{"detail": fiberErr.Message})
			}
			return c.Status(fiber.StatusInternalServerError).JSON(fiber.Map{"detail": "internal server error"})
		},
	})
	app.Get("/health", func(c fiber.Ctx) error {
		return c.JSON(fiber.Map{"status": "ok"})
	})
	h.Register(app)
	return app
}

func doJSON(t *testing.T, app *fiber.App, method, path string, body any) *http.Response {
	t.Helper()
	var reader *bytes.Reader
	if body != nil {
		b, err := json.Marshal(body)
		require.NoError(t, err)
		reader = bytes.NewReader(b)
	} else {
		reader = bytes.NewReader(nil)
	}
	req := httptest.NewRequest(method, path, reader)
	req.Header.Set("Content-Type", "application/json")
	resp, err := app.Test(req)
	require.NoError(t, err)
	return resp
}

func decode(t *testing.T, resp *http.Response) map[string]any {
	t.Helper()
	var out map[string]any
	require.NoError(t, json.NewDecoder(resp.Body).Decode(&out))
	return out
}

func TestCreateAndGetItem(t *testing.T) {
	app := newTestApp(t)

	createResp := doJSON(t, app, http.MethodPost, "/v1/items/", map[string]string{"name": "widget", "description": "a widget"})
	require.Equal(t, http.StatusCreated, createResp.StatusCode)
	created := decode(t, createResp)

	getResp := doJSON(t, app, http.MethodGet, "/v1/items/"+created["id"].(string), nil)
	require.Equal(t, http.StatusOK, getResp.StatusCode)
	require.Equal(t, "widget", decode(t, getResp)["name"])
}

func TestGetMissingItem404s(t *testing.T) {
	app := newTestApp(t)

	resp := doJSON(t, app, http.MethodGet, "/v1/items/00000000-0000-0000-0000-000000000000", nil)
	require.Equal(t, http.StatusNotFound, resp.StatusCode)
}

func TestListItems(t *testing.T) {
	app := newTestApp(t)

	doJSON(t, app, http.MethodPost, "/v1/items/", map[string]string{"name": "a"})
	doJSON(t, app, http.MethodPost, "/v1/items/", map[string]string{"name": "b"})

	resp := doJSON(t, app, http.MethodGet, "/v1/items/", nil)
	require.Equal(t, http.StatusOK, resp.StatusCode)
	var items []map[string]any
	require.NoError(t, json.NewDecoder(resp.Body).Decode(&items))
	require.Len(t, items, 2)
}

func TestDeleteItem(t *testing.T) {
	app := newTestApp(t)

	createResp := doJSON(t, app, http.MethodPost, "/v1/items/", map[string]string{"name": "to-delete"})
	id := decode(t, createResp)["id"].(string)

	deleteResp := doJSON(t, app, http.MethodDelete, "/v1/items/"+id, nil)
	require.Equal(t, http.StatusNoContent, deleteResp.StatusCode)

	getResp := doJSON(t, app, http.MethodGet, "/v1/items/"+id, nil)
	require.Equal(t, http.StatusNotFound, getResp.StatusCode)
}

func TestHealthCheck(t *testing.T) {
	app := newTestApp(t)

	resp := doJSON(t, app, http.MethodGet, "/health", nil)
	require.Equal(t, http.StatusOK, resp.StatusCode)
	require.Equal(t, "ok", decode(t, resp)["status"])
}
