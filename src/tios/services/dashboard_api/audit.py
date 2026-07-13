"""Confined append-only audit file access for local dashboard actions."""

from __future__ import annotations

import os
import secrets
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO


class AuditPathError(ValueError):
    """An audit path cannot be opened without escaping its repository boundary."""


def _validate_relative_path(relative_path: Path) -> None:
    if (
        relative_path.is_absolute()
        or len(relative_path.parts) < 2
        or any(part in {"", ".", ".."} for part in relative_path.parts)
    ):
        raise AuditPathError("dashboard audit path must be a confined relative file")


def _verify_entry(parent_fd: int, name: str, descriptor: int, *, directory: bool) -> None:
    opened = os.fstat(descriptor)
    linked = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if (
        not expected(linked.st_mode)
        or (not directory and (opened.st_nlink != 1 or linked.st_nlink != 1))
        or (opened.st_dev, opened.st_ino) != (linked.st_dev, linked.st_ino)
    ):
        raise AuditPathError("dashboard audit path is unsafe")


@contextmanager
def confined_audit_handle(
    root: Path, relative_path: Path, *, create: bool
) -> Iterator[TextIO | None]:
    """Open a relative audit through anchored, no-follow repository parents."""
    _validate_relative_path(relative_path)
    descriptors: list[int] = []
    handle: TextIO | None = None
    try:
        root_fd = os.open(
            Path(os.path.realpath(root)), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        descriptors.append(root_fd)
        parent_fd = root_fd
        for component in relative_path.parent.parts:
            if create:
                try:
                    os.mkdir(component, 0o700, dir_fd=parent_fd)
                except FileExistsError:
                    pass
            try:
                child_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent_fd,
                )
            except FileNotFoundError:
                if not create:
                    yield None
                    return
                raise
            except OSError as error:
                raise AuditPathError(
                    "dashboard audit path parent is not a real directory"
                ) from error
            _verify_entry(parent_fd, component, child_fd, directory=True)
            descriptors.append(child_fd)
            parent_fd = child_fd
        flags = (
            os.O_NOFOLLOW
            | os.O_NONBLOCK
            | (os.O_CREAT | os.O_RDWR | os.O_APPEND if create else os.O_RDONLY)
        )
        try:
            file_fd = os.open(relative_path.name, flags, 0o600, dir_fd=parent_fd)
        except FileNotFoundError:
            if not create:
                yield None
                return
            raise
        except OSError as error:
            raise AuditPathError("dashboard audit path file is unsafe") from error
        _verify_entry(parent_fd, relative_path.name, file_fd, directory=False)
        handle = os.fdopen(file_fd, "a+" if create else "r", encoding="utf-8")
        yield handle
        _verify_entry(parent_fd, relative_path.name, handle.fileno(), directory=False)
        for anchor, component, child in zip(
            descriptors[:-1], relative_path.parent.parts, descriptors[1:], strict=True
        ):
            _verify_entry(anchor, component, child, directory=True)
    finally:
        if handle is not None:
            handle.close()
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def confined_atomic_write(root: Path, relative_path: Path, content: bytes) -> None:
    """Atomically replace one confined regular file without following links."""
    _validate_relative_path(relative_path)
    if not isinstance(content, bytes):
        raise AuditPathError("dashboard atomic content must be bytes")
    descriptors: list[int] = []
    temporary_fd: int | None = None
    temporary_name: str | None = None
    try:
        root_fd = os.open(
            Path(os.path.realpath(root)), os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        )
        descriptors.append(root_fd)
        parent_fd = root_fd
        for component in relative_path.parent.parts:
            try:
                child_fd = os.open(
                    component,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent_fd,
                )
            except OSError as error:
                raise AuditPathError(
                    "dashboard atomic path parent is not a real directory"
                ) from error
            _verify_entry(parent_fd, component, child_fd, directory=True)
            descriptors.append(child_fd)
            parent_fd = child_fd

        try:
            existing_fd = os.open(
                relative_path.name,
                os.O_RDONLY | os.O_NONBLOCK | os.O_NOFOLLOW,
                dir_fd=parent_fd,
            )
        except FileNotFoundError:
            existing_fd = None
        except OSError as error:
            raise AuditPathError("dashboard atomic destination is unsafe") from error
        if existing_fd is not None:
            try:
                _verify_entry(parent_fd, relative_path.name, existing_fd, directory=False)
            finally:
                os.close(existing_fd)

        temporary_name = f".{relative_path.name}.{os.getpid()}.{secrets.token_hex(8)}.temporary"
        temporary_fd = os.open(
            temporary_name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
            dir_fd=parent_fd,
        )
        _verify_entry(parent_fd, temporary_name, temporary_fd, directory=False)
        remaining = memoryview(content)
        while remaining:
            written = os.write(temporary_fd, remaining)
            if written <= 0:
                raise OSError("dashboard atomic write made no progress")
            remaining = remaining[written:]
        os.fsync(temporary_fd)
        _verify_entry(parent_fd, temporary_name, temporary_fd, directory=False)
        os.replace(
            temporary_name,
            relative_path.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        temporary_name = None
        _verify_entry(parent_fd, relative_path.name, temporary_fd, directory=False)
        os.fsync(parent_fd)
        for anchor, component, child in zip(
            descriptors[:-1], relative_path.parent.parts, descriptors[1:], strict=True
        ):
            _verify_entry(anchor, component, child, directory=True)
    except AuditPathError:
        raise
    except OSError as error:
        raise AuditPathError("dashboard atomic write failed safely") from error
    finally:
        if temporary_fd is not None:
            os.close(temporary_fd)
        if temporary_name is not None and descriptors:
            try:
                os.unlink(temporary_name, dir_fd=descriptors[-1])
            except FileNotFoundError:
                pass
        for descriptor in reversed(descriptors):
            os.close(descriptor)
