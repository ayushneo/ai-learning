// Package db opens the GORM connection pool. No lifespan-state dance needed
// -- *gorm.DB is just a struct main.go holds and passes to repositories
// directly, and Close() at shutdown is the direct equivalent of
// fastapi_template's engine.dispose().
package db

import (
	"time"

	"gorm.io/driver/postgres"
	"gorm.io/gorm"
)

func Open(dsn string) (*gorm.DB, error) {
	db, err := gorm.Open(postgres.Open(dsn), &gorm.Config{})
	if err != nil {
		return nil, err
	}
	sqlDB, err := db.DB()
	if err != nil {
		return nil, err
	}
	sqlDB.SetMaxOpenConns(20)
	sqlDB.SetMaxIdleConns(5)
	sqlDB.SetConnMaxLifetime(time.Hour)
	return db, nil
}
