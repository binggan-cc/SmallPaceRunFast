// Package service implements business logic.
package service

import (
	"fmt"
	"strings"

	"github.com/example/goproject/pkg/models"
)

// UserService handles user-related operations.
type UserService struct {
	prefix string
}

// NewUserService constructs a UserService with default settings.
func NewUserService() *UserService {
	return &UserService{prefix: "Hello"}
}

// Greet returns a greeting string for the given user.
func (s *UserService) Greet(u *models.User) string {
	return fmt.Sprintf("%s, %s!", s.prefix, u.Name)
}

// GreetAll returns greetings for multiple users.
func (s *UserService) GreetAll(users []*models.User) []string {
	results := make([]string, 0, len(users))
	for _, u := range users {
		results = append(results, s.Greet(u))
	}
	return results
}

// normalizePrefix trims and lowercases the service prefix.
func normalizePrefix(prefix string) string {
	return strings.ToLower(strings.TrimSpace(prefix))
}
