"""Database-FREE tests: PostgreSQL is the only supported database configuration.

The settings module is executed in isolation with a controlled environment (env files are not
loaded and the real process environment is untouched), so no database connection is made."""
import os
import runpy
from pathlib import Path
from unittest import mock

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.test import SimpleTestCase

SETTINGS_PATH = Path(settings.BASE_DIR) / "config" / "settings.py"
BASE_ENV = {
    "DJANGO_SECRET_KEY": "x" * 50,
    "DB_NAME": "example_database",
    "DB_USER": "example_user",
    "DB_PASSWORD": "example-not-a-real-password",
    "DJANGO_ENV_FILE": str(Path(__file__).with_name("does_not_exist.env")),
}


def load_settings(**overrides):
    env = {**BASE_ENV, **overrides}
    env = {key: value for key, value in env.items() if value is not None}
    with mock.patch.dict(os.environ, env, clear=True), mock.patch("dotenv.load_dotenv"):
        return runpy.run_path(str(SETTINGS_PATH))


class PostgresOnlySettingsTests(SimpleTestCase):
    def test_live_settings_use_only_a_postgresql_default_database(self):
        self.assertEqual(set(settings.DATABASES), {"default"})
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(getattr(settings, "DATABASE_ROUTERS", []), [])

    def test_engine_defaults_to_postgresql_without_db_engine_variable(self):
        db = load_settings()["DATABASES"]["default"]
        self.assertEqual(db["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(db["PORT"], "5432")
        self.assertEqual(db["HOST"], "127.0.0.1")
        self.assertEqual(db["NAME"], "example_database")

    def test_mysql_or_mariadb_engine_is_rejected_not_used_as_fallback(self):
        for engine in ("django.db.backends.mysql", "mysql", "django.db.backends.sqlite3"):
            with self.subTest(engine=engine), self.assertRaises(ImproperlyConfigured):
                load_settings(DB_ENGINE=engine)

    def test_mariadb_default_port_is_rejected(self):
        with self.assertRaises(ImproperlyConfigured):
            load_settings(DB_PORT="3306")

    def test_missing_required_database_variables_fail_clearly(self):
        for name in ("DB_NAME", "DB_USER", "DB_PASSWORD"):
            with self.subTest(variable=name), self.assertRaises(ImproperlyConfigured):
                load_settings(**{name: None})

    def test_environment_file_defaults_to_postgres_file(self):
        namespace = load_settings(DJANGO_ENV_FILE=None)
        self.assertEqual(namespace["ENV_FILE"].name, ".env.postgres")
        self.assertEqual(namespace["ENV_FILE"].parent, Path(settings.BASE_DIR))

    def test_explicit_environment_file_selection_still_works(self):
        namespace = load_settings(DJANGO_ENV_FILE="custom.env")
        self.assertEqual(namespace["ENV_FILE"], Path(settings.BASE_DIR) / "custom.env")
