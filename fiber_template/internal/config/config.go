// Package config loads settings from the environment. Stdlib os.Getenv, no
// viper/envconfig -- five string fields don't earn a struct-tag reflection
// dependency; pydantic-settings on the Python side earns its keep because it
// also validates/coerces types, which os.Getenv doesn't need to fake here.
package config

import "os"

type Config struct {
	DatabaseURL string
	Port        string
	Env         string
}

func Load() Config {
	return Config{
		DatabaseURL: getenv("DATABASE_URL", "postgres://postgres:postgres@localhost:5432/app?sslmode=disable"),
		Port:        getenv("PORT", "8000"),
		Env:         getenv("APP_ENV", "development"),
	}
}

func getenv(key, fallback string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return fallback
}
