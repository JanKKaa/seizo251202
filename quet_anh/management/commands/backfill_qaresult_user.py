import re
from collections import defaultdict

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from quet_anh.models import QAResult


def normalize_name(value: str) -> str:
    if not value:
        return ""
    text = value.replace("\u3000", " ").strip().lower()
    text = re.sub(r"\s+", " ", text)
    return text


class Command(BaseCommand):
    help = "Backfill QAResult.user from legacy operator_name for cleaner dashboard aggregation."

    # Explicit aliases for names seen in real data.
    ALIASES = {
        "hung": "phanvanhung",
        "hung hung": "phanvanhung",
        "フン ファンヴァン": "phanvanhung",
        "bao": "nguyenvanbao",
        "グエン ヴァン バオ": "nguyenvanbao",
        "グエン ヴァンバオ": "nguyenvanbao",
        "早川": "hayakawa_yuuki",
        "早川 祐貴": "hayakawa_yuuki",
        "向山": "mukaiyama",
        "向山 光昭": "mukaiyama",
        "滝沢 颯人": "T.hayato11",
        "中村 祐貴": "Ny0106",
        # duplicated identities: choose current actively-used account.
        "中村 隼人": "hayato.N",
        "隼人 中村": "hayato.N",
        "中村": "hayato.N",
        "宮坂 徹": "Miyasaka",
        "宮坂": "Miyasaka",
        "柴 拓之": "SHIBA",
        "拓之 柴": "SHIBA",
        "柴": "SHIBA",
        "ジャン": "giang",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Apply update. Without this flag, command runs in dry-run mode.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Process up to N rows (0 = no limit).",
        )

    def _build_auto_index(self):
        index = defaultdict(set)
        users = User.objects.all()
        for user in users:
            keys = {
                normalize_name(user.username),
                normalize_name(user.first_name),
                normalize_name(user.last_name),
            }
            full_name = f"{(user.last_name or '').strip()} {(user.first_name or '').strip()}".strip()
            reverse_full_name = f"{(user.first_name or '').strip()} {(user.last_name or '').strip()}".strip()
            keys.add(normalize_name(full_name))
            keys.add(normalize_name(reverse_full_name))
            for key in keys:
                if key:
                    index[key].add(user.id)
        return index

    def _resolve_user(self, operator_name, auto_index):
        key = normalize_name(operator_name)
        if not key:
            return None, "empty"

        alias_username = self.ALIASES.get(operator_name) or self.ALIASES.get(key)
        if alias_username:
            target = User.objects.filter(username=alias_username).first()
            if target:
                return target, "alias"

        candidates = list(auto_index.get(key, set()))
        if len(candidates) == 1:
            return User.objects.filter(id=candidates[0]).first(), "auto_unique"
        if len(candidates) > 1:
            return None, "ambiguous"
        return None, "unmatched"

    def handle(self, *args, **options):
        apply_changes = options["apply"]
        limit = int(options["limit"] or 0)

        qs = QAResult.objects.filter(user__isnull=True).exclude(operator_name="")
        if limit > 0:
            qs = qs.order_by("id")[:limit]
        rows = list(qs)

        auto_index = self._build_auto_index()
        updates = []
        unresolved = defaultdict(int)
        resolved_by_operator = defaultdict(int)
        source_counter = defaultdict(int)

        for row in rows:
            user, source = self._resolve_user(row.operator_name, auto_index)
            if user:
                updates.append((row.id, user.id, row.operator_name, user.username, source))
                resolved_by_operator[row.operator_name] += 1
                source_counter[source] += 1
            else:
                unresolved[row.operator_name] += 1
                source_counter[source] += 1

        self.stdout.write(self.style.NOTICE(f"target_rows={len(rows)}"))
        self.stdout.write(self.style.NOTICE(f"resolved_rows={len(updates)}"))
        self.stdout.write(self.style.NOTICE(f"unresolved_rows={sum(unresolved.values())}"))
        self.stdout.write(f"resolve_sources={dict(source_counter)}")

        if resolved_by_operator:
            self.stdout.write("\n[resolved by operator_name]")
            for name, cnt in sorted(resolved_by_operator.items(), key=lambda x: x[1], reverse=True):
                self.stdout.write(f"- {name}: {cnt}")

        if unresolved:
            self.stdout.write("\n[unresolved operator_name]")
            for name, cnt in sorted(unresolved.items(), key=lambda x: x[1], reverse=True):
                self.stdout.write(f"- {name}: {cnt}")

        if not apply_changes:
            self.stdout.write(self.style.WARNING("\nDry-run only. Add --apply to update DB."))
            return

        with transaction.atomic():
            for row_id, user_id, _, _, _ in updates:
                QAResult.objects.filter(id=row_id, user__isnull=True).update(user_id=user_id)

        self.stdout.write(self.style.SUCCESS(f"\nApplied: updated {len(updates)} QAResult rows."))

