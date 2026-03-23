from django.db import migrations


CREATE_XULYANH2_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS "xu_ly_anh_xulyanh2" (
    "id" integer NOT NULL PRIMARY KEY AUTOINCREMENT,
    "machine_number" integer unsigned NOT NULL CHECK ("machine_number" >= 0),
    "image" varchar(100) NOT NULL,
    "processed_image" varchar(100) NULL,
    "data" text NOT NULL,
    "result" varchar(255) NOT NULL,
    "created_at" datetime NOT NULL,
    "machine_id" bigint NULL REFERENCES "xu_ly_anh_deviceinfo" ("id") DEFERRABLE INITIALLY DEFERRED,
    "user_id" integer NULL REFERENCES "auth_user" ("id") DEFERRABLE INITIALLY DEFERRED
);
"""


CREATE_XULYANH2_INDEX_MACHINE_SQL = """
CREATE INDEX IF NOT EXISTS "xu_ly_anh_xulyanh2_machine_id_2207558c"
ON "xu_ly_anh_xulyanh2" ("machine_id");
"""


CREATE_XULYANH2_INDEX_USER_SQL = """
CREATE INDEX IF NOT EXISTS "xu_ly_anh_xulyanh2_user_id_b824ba18"
ON "xu_ly_anh_xulyanh2" ("user_id");
"""


class Migration(migrations.Migration):
    dependencies = [
        ("xu_ly_anh", "0001_initial"),
    ]

    operations = [
        migrations.RunSQL(
            sql=CREATE_XULYANH2_TABLE_SQL,
            reverse_sql=migrations.RunSQL.noop,
        ),
        migrations.RunSQL(
            sql=CREATE_XULYANH2_INDEX_MACHINE_SQL,
            reverse_sql='DROP INDEX IF EXISTS "xu_ly_anh_xulyanh2_machine_id_2207558c";',
        ),
        migrations.RunSQL(
            sql=CREATE_XULYANH2_INDEX_USER_SQL,
            reverse_sql='DROP INDEX IF EXISTS "xu_ly_anh_xulyanh2_user_id_b824ba18";',
        ),
    ]

