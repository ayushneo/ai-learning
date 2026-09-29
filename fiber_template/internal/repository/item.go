package repository

import (
	"gorm.io/gorm"

	"fiber-template/internal/models"
)

type ItemRepository struct {
	Base[models.Item]
}

func NewItemRepository(db *gorm.DB) *ItemRepository {
	return &ItemRepository{Base[models.Item]{DB: db}}
}
