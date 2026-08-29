from collections import defaultdict

from app.db.models import CredentialKind

SLOT_ORDER = ["machine", "vault", "become"]

SLOT_BY_KIND: dict[CredentialKind, str] = {
    CredentialKind.ssh_key: "machine",
    CredentialKind.ssh_password: "machine",
    CredentialKind.vault_password: "vault",
    CredentialKind.become_password: "become",
}

SLOT_LABEL = {
    "machine": "machine (SSH)",
    "vault": "vault password",
    "become": "become password",
}


def find_slot_conflict(rows: list[tuple[str, CredentialKind]]) -> tuple[str, list[str]] | None:
    """rows = [(credential_name, kind)]. Return (slot, sorted names) for first slot holding >1 credential, else None."""
    by_slot: dict[str, list[str]] = defaultdict(list)
    for name, kind in rows:
        slot = SLOT_BY_KIND.get(kind)
        if slot:
            by_slot[slot].append(name)

    for slot in SLOT_ORDER:
        names = by_slot.get(slot, [])
        if len(names) > 1:
            return (slot, sorted(names))
    return None
