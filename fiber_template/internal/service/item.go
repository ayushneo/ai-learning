// Business logic sits here, not in the handler or the repository. For CRUD
// this thin, the service is nearly a pass-through -- expected and fine. The
// payoff shows up the moment a use case needs more than one repository call,
// a permission check, or an outbound call; the handler still just calls one
// service method either way.
package service

import (
	"fmt"

	"github.com/google/uuid"

	"fiber-template/internal/apperror"
	"fiber-template/internal/models"
	"fiber-template/internal/repository"
)

type ItemService struct {
	repo *repository.ItemRepository
}

func NewItemService(repo *repository.ItemRepository) *ItemService {
	return &ItemService{repo: repo}
}

type CreateItemInput struct {
	Name        string
	Description *string
}

func (s *ItemService) Create(in CreateItemInput) (*models.Item, error) {
	item := &models.Item{ID: uuid.New(), Name: in.Name, Description: in.Description}
	if err := s.repo.Create(item); err != nil {
		return nil, err
	}
	return item, nil
}

func (s *ItemService) Get(id uuid.UUID) (*models.Item, error) {
	item, err := s.repo.Get(id)
	if err != nil {
		return nil, err
	}
	if item == nil {
		return nil, apperror.NotFound(fmt.Sprintf("item %s not found", id))
	}
	return item, nil
}

func (s *ItemService) List(limit, offset int) ([]models.Item, error) {
	return s.repo.List(limit, offset)
}

func (s *ItemService) Delete(id uuid.UUID) error {
	item, err := s.Get(id)
	if err != nil {
		return err
	}
	return s.repo.Delete(item)
}
