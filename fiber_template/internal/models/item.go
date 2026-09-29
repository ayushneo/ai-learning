// Package models holds GORM structs (DB shape). Example resource -- delete
// this file (and its repository/service/handler) once you've copied the
// pattern for your real resources; it's here to be read, not to ship.
package models

import (
	"time"

	"github.com/google/uuid"
)

type Item struct {
	ID          uuid.UUID `gorm:"type:uuid;primaryKey"`
	Name        string    `gorm:"size:200;not null"`
	Description *string   `gorm:"size:2000"`
	// CreatedAt: no explicit default tag -- GORM auto-populates any field
	// named exactly CreatedAt on Create, portable across Postgres/SQLite
	// (Postgres's now() isn't valid SQL for the sqlite driver tests use).
	CreatedAt time.Time `gorm:"not null"`
}
