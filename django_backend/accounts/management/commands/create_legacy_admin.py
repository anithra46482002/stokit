from getpass import getpass

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from accounts.hashers import hash_password
from accounts.models import AdminRoleAssignment
from legacydb.models import AdminAccount


class Command(BaseCommand):
    help = (
        "Create a React-admin-compatible account in the legacy admins table "
        "and assign an explicit role. Requires an approved, initialized schema."
    )

    def add_arguments(self, parser):
        parser.add_argument("--id", type=int, required=True, help="Explicit legacy admins.id (not auto-increment).")
        parser.add_argument("--username", required=True)
        parser.add_argument("--email", required=True)
        parser.add_argument("--fullname", default="")
        parser.add_argument("--role", choices=["SUPER_ADMIN", "ADMIN", "WAREHOUSE_STAFF"], required=True)
        parser.add_argument("--assigned-by", type=int, help="Existing active Super Admin's legacy admins.id.")
        parser.add_argument(
            "--bootstrap-super-admin",
            action="store_true",
            help="One-time bootstrap when no active Super Admin exists; requires --role SUPER_ADMIN.",
        )

    def handle(self, *args, **options):
        admin_id = options["id"]
        username = options["username"].strip()
        email = options["email"].strip()
        fullname = options["fullname"].strip()
        role = options["role"]
        actor_id = options.get("assigned_by")
        bootstrap = options["bootstrap_super_admin"]

        if admin_id <= 0 or not username or not email:
            raise CommandError("--id must be positive; --username and --email must not be empty.")
        if bootstrap and (role != "SUPER_ADMIN" or actor_id is not None):
            raise CommandError("--bootstrap-super-admin requires --role SUPER_ADMIN and no --assigned-by.")

        db_config = settings.DATABASES["default"]
        database_name = db_config.get("NAME")
        allowed_targets = {"stokit_dev", "stokit_legacy_test", "stokit_postgres_dev"}
        if database_name not in allowed_targets:
            raise CommandError(
                "This provisioning command is restricted to: " + ", ".join(sorted(allowed_targets)) + "."
            )
        # The new PostgreSQL development target must match its exact local endpoint.
        # This prevents accidental account creation on another database with the same name.
        if database_name == "stokit_postgres_dev":
            if (
                db_config.get("ENGINE") != "django.db.backends.postgresql"
                or db_config.get("HOST") not in {"127.0.0.1", "localhost"}
                or str(db_config.get("PORT", "5432")) != "5432"
            ):
                raise CommandError(
                    "stokit_postgres_dev account bootstrap is restricted to local PostgreSQL on port 5432."
                )
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT current_database(), current_schema(), "
                        "host(inet_server_addr()), inet_server_port()"
                    )
                    actual_database, actual_schema, actual_host, actual_port = cursor.fetchone()
            except Exception as exc:
                raise CommandError("Could not verify the PostgreSQL target; no account was created.") from exc
            if (
                actual_database != "stokit_postgres_dev"
                or actual_schema != "public"
                or actual_host not in {"127.0.0.1", "::1"}
                or actual_port != 5432
            ):
                raise CommandError(
                    "Connected PostgreSQL target did not match stokit_postgres_dev/public on localhost:5432; "
                    "no account was created."
                )

        # Do not attempt account creation when either required table is absent.
        try:
            tables = set(connection.introspection.table_names())
        except Exception as exc:
            raise CommandError("Database schema is unavailable; no account was created.") from exc
        required = {"admins", "accounts_adminroleassignment"}
        missing = sorted(required - tables)
        if missing:
            raise CommandError(
                "Required table(s) missing: " + ", ".join(missing)
                + ". Obtain schema approval and provision the approved development schema first; no account was created."
            )

        password = getpass("Password (input hidden): ")
        confirmation = getpass("Confirm password (input hidden): ")
        if not password:
            raise CommandError("Password must not be empty.")
        if password != confirmation:
            raise CommandError("Passwords do not match.")
        encoded_password = hash_password(password)

        with transaction.atomic():
            if AdminAccount.objects.filter(pk=admin_id).exists():
                raise CommandError("That legacy admin ID already exists.")
            if AdminAccount.objects.filter(username=username).exists():
                raise CommandError("That legacy admin username already exists.")
            if AdminAccount.objects.filter(email=email).exists():
                raise CommandError("That legacy admin email already exists.")

            has_super = AdminRoleAssignment.objects.filter(role="SUPER_ADMIN", active=True).exists()
            if not has_super:
                if not (bootstrap and role == "SUPER_ADMIN" and actor_id is None):
                    raise CommandError(
                        "No active Super Admin exists. For the first verified admin only, "
                        "use --role SUPER_ADMIN --bootstrap-super-admin."
                    )
            else:
                if actor_id is None:
                    raise CommandError("--assigned-by is required when an active Super Admin already exists.")
                actor = AdminRoleAssignment.objects.filter(
                    principal_type="ADMIN", principal_id=actor_id,
                    role="SUPER_ADMIN", active=True,
                ).first()
                if actor is None:
                    raise CommandError("--assigned-by must identify an active Super Admin.")

            # The legacy table has required columns not represented on AdminAccount.
            # Supply empty values for those legacy-only fields; never write a plaintext password.
            with connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO admins "
                    "(id, username, email, fullname, password, phone, address, \"paymentDate\", token, api_token, last_login) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NULL, NULL)",
                    [admin_id, username, email, fullname or None, encoded_password, "", "", "", ""],
                )

            AdminRoleAssignment.objects.create(
                principal_type="ADMIN",
                principal_id=admin_id,
                role=role,
                active=True,
                assigned_by_admin_id=actor_id,
            )

        self.stdout.write(self.style.SUCCESS(
            f"Created legacy admin account id {admin_id} and assigned role {role}. "
            "No password was displayed."
        ))
