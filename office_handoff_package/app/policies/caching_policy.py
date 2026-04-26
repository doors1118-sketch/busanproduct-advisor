"""
Caching Policy — Core Prompt 해시 검증
"""
import hashlib


def compute_core_hash(core_text: str) -> str:
    return hashlib.sha256(core_text.encode("utf-8")).hexdigest()


def compute_prefix_hash(prefix_text: str) -> str:
    return hashlib.sha256(prefix_text.encode("utf-8")).hexdigest()


def validate_cache_invariant(current_hash: str, expected_hash: str) -> bool:
    if current_hash != expected_hash:
        raise AssertionError(
            f"Core prompt hash changed! expected={expected_hash[:16]}... "
            f"got={current_hash[:16]}..."
        )
    return True
