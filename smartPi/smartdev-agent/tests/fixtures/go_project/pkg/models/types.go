// Package models — shared interfaces and type aliases.
package models

// Stringer is a local interface mirroring fmt.Stringer.
type Stringer interface {
	String() string
}

// Validator is implemented by types that can validate themselves.
type Validator interface {
	Validate() error
}

// ID is a type alias for string used as entity identifiers.
type ID = string
