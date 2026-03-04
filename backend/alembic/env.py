from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context
from alembic.operations import ops
from api.models.metadata import metadata
from config.database import database_config

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = metadata
config.set_main_option("sqlalchemy.url", str(database_config.POSTGRES_DATABASE_URI))


def process_revision_directives(context, revision, directives):
    """Auto-generate triggers for updated_at columns."""
    script = directives[0]
    tables_with_updated_at = set()

    def find_updated_at_tables(operations):
        for op in operations:
            if isinstance(op, ops.CreateTableOp):
                for column in op.columns:
                    if column.name == "updated_at":
                        tables_with_updated_at.add(op.table_name)
                        break
            elif hasattr(op, "ops"):
                find_updated_at_tables(op.ops)

    if script.upgrade_ops:
        find_updated_at_tables(script.upgrade_ops.ops)

    if not tables_with_updated_at:
        return

    # 1. Create Function (if it doesn't exist)
    func_sql = (
        "CREATE OR REPLACE FUNCTION update_updated_at_column() "
        "RETURNS TRIGGER AS $$ BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ language 'plpgsql';"
    )
    script.upgrade_ops.ops.insert(0, ops.ExecuteSQLOp(func_sql))

    # 2. Add Triggers
    for table in sorted(tables_with_updated_at):
        trigger_name = f"update_{table}_updated_at"
        trigger_sql = f"CREATE TRIGGER {trigger_name} BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();"
        script.upgrade_ops.ops.append(ops.ExecuteSQLOp(trigger_sql))

        if script.downgrade_ops:
            script.downgrade_ops.ops.insert(0, ops.ExecuteSQLOp(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table}"))

    # 3. Drop Function on Downgrade
    if script.downgrade_ops:
        script.downgrade_ops.ops.append(ops.ExecuteSQLOp("DROP FUNCTION IF EXISTS update_updated_at_column"))


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        process_revision_directives=process_revision_directives,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_server_default=True,
            process_revision_directives=process_revision_directives,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
