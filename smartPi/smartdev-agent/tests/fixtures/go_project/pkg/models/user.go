// Package models defines core data structures.
package models

import "fmt"

// User represents an application user.
type User struct {
	Name string
	Age  int
}

// NewUser constructs a User with the given name and age.
func NewUser(name string, age int) *User {
	return &User{Name: name, Age: age}
}

// String implements fmt.Stringer for User.
func (u *User) String() string {
	return fmt.Sprintf("%s (%d)", u.Name, u.Age)
}

// Validate checks that the user fields are valid.
func (u *User) Validate() error {
	if u.Name == "" {
		return fmt.Errorf("name is required")
	}
	if u.Age < 0 {
		return fmt.Errorf("age must be non-negative")
	}
	return nil
}
