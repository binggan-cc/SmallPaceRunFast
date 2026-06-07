// Package main — entry point for goproject fixture
package main

import (
	"fmt"
	"os"

	"github.com/example/goproject/internal/service"
	"github.com/example/goproject/pkg/models"
)

func main() {
	user := models.NewUser("Alice", 30)
	svc := service.NewUserService()

	result := svc.Greet(user)
	fmt.Println(result)
	os.Exit(0)
}

// Run executes the main workflow and returns an error if any.
func Run(args []string) error {
	if len(args) == 0 {
		return fmt.Errorf("no args provided")
	}
	return nil
}
