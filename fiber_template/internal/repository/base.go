// Package repository holds one generic CRUD base (Go generics, type
// parameter on the model) instead of a get/create/delete trio hand-written
// per resource -- the same call fastapi_template's BaseRepository makes.
//
// Repositories only talk GORM. No transaction handling here -- the caller
// (service, or the handler for trivial resources) owns that boundary, so two
// repository calls can share one *gorm.DB (already a transaction, see
// service/item.go) when a use case spans more than one table.
package repository

import (
	"github.com/google/uuid"
	"gorm.io/gorm"
)

type Base[T any] struct {
	DB *gorm.DB
}

func (r *Base[T]) Get(id uuid.UUID) (*T, error) {
	var m T
	if err := r.DB.First(&m, "id = ?", id).Error; err != nil {
		if err == gorm.ErrRecordNotFound {
			return nil, nil
		}
		return nil, err
	}
	return &m, nil
}

// ponytail: OFFSET/LIMIT pagination -- simplest thing that works, but OFFSET
// still scans and discards `offset` rows server-side, so cost grows with
// page depth. Fine well past most APIs' real page counts; switch to keyset
// pagination (WHERE id > :last_id ORDER BY id) if you ever see someone
// paginating deep into millions of rows. Same call fastapi_template makes,
// same ceiling.
func (r *Base[T]) List(limit, offset int) ([]T, error) {
	var out []T
	if err := r.DB.Limit(limit).Offset(offset).Find(&out).Error; err != nil {
		return nil, err
	}
	return out, nil
}

func (r *Base[T]) Create(m *T) error {
	return r.DB.Create(m).Error
}

func (r *Base[T]) Delete(m *T) error {
	return r.DB.Delete(m).Error
}
