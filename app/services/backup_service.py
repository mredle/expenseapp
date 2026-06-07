# coding=utf-8
"""Backup service — logical backup and restore for all domain objects."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import tarfile
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from flask import current_app
from sqlalchemy import or_

from app import db
from app.models import (
    BackupSegment,
    BackupSet,
    Challenge,
    Credential,
    Currency,
    Event,
    EventCurrency,
    EventUser,
    Expense,
    File,
    Image,
    Log,
    Message,
    Notification,
    Post,
    Settlement,
    Task,
    Thumbnail,
    User,
)
from app.storage import get_storage_provider

# ---------------------------------------------------------------------------
# Format version — bump when serialized schema changes
# ---------------------------------------------------------------------------
BACKUP_FORMAT_VERSION = '1.0'

# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class PaginatedResult:
    """Generic paginated query result."""

    items: list[Any]
    has_next: bool
    has_prev: bool
    next_num: int | None
    prev_num: int | None
    total: int


@dataclass
class BackupResult:
    """Outcome of a backup creation or deletion operation."""

    success: bool
    backup_set: BackupSet | None = None
    error: str | None = None


@dataclass
class RestoreResult:
    """Outcome of a restore operation."""

    success: bool
    backup_set: BackupSet | None = None
    restored_counts: dict[str, int] | None = None
    error: str | None = None


@dataclass
class ExportResult:
    """Outcome of an export operation."""

    success: bool
    archive_bytes: bytes | None = None
    filename: str | None = None
    error: str | None = None


@dataclass
class ImportResult:
    """Outcome of an import operation."""

    success: bool
    backup_set: BackupSet | None = None
    error: str | None = None


# ---------------------------------------------------------------------------
# Internal helpers — get the storage provider for backups
# ---------------------------------------------------------------------------

def _get_backup_storage() -> Any:
    """Return the storage provider configured for backups."""
    backend = current_app.config.get('BACKUP_STORAGE_BACKEND') or \
              current_app.config.get('STORAGE_DEFAULT_BACKEND', 'local')
    return get_storage_provider(backend)


def _backup_backend_name() -> str:
    """Return the effective storage backend name for backups."""
    return current_app.config.get('BACKUP_STORAGE_BACKEND') or \
           current_app.config.get('STORAGE_DEFAULT_BACKEND', 'local')


def _backup_root() -> str:
    """Return the root path prefix for all backup sets."""
    return current_app.config.get('BACKUP_STORAGE_PATH', 'backups')


# ---------------------------------------------------------------------------
# Internal helpers — media serialization
# ---------------------------------------------------------------------------

def _file_to_dict(file_obj: File) -> dict[str, Any]:
    """Serialize a :class:`File` record (without binary content) to dict."""
    return {
        'guid': str(file_obj.guid),
        'original_filename': file_obj.original_filename,
        'storage_backend': file_obj.storage_backend,
        'storage_key': file_obj.storage_key,
        'mime_type': file_obj.mime_type,
        'file_size': file_obj.file_size,
        'file_hash': file_obj.file_hash,
        'hash_algorithm': file_obj.hash_algorithm,
        'db_created_at': _dt(file_obj.db_created_at),
        'db_updated_at': _dt(file_obj.db_updated_at),
        'db_created_by': file_obj.db_created_by,
        'db_updated_by': file_obj.db_updated_by,
    }


def _image_to_dict(image: Image) -> dict[str, Any]:
    """Serialize an :class:`Image` record to dict."""
    return {
        'guid': str(image.guid),
        'file_guid': str(image.file.guid) if image.file else None,
        'is_vector': image.is_vector,
        'width': image.width,
        'height': image.height,
        'rotate': image.rotate,
        'format': image.format,
        'mode': image.mode,
        'description': image.description,
        'db_created_at': _dt(image.db_created_at),
        'db_updated_at': _dt(image.db_updated_at),
        'db_created_by': image.db_created_by,
        'db_updated_by': image.db_updated_by,
    }


def _thumbnail_to_dict(thumb: Thumbnail) -> dict[str, Any]:
    """Serialize a :class:`Thumbnail` record to dict."""
    return {
        'guid': str(thumb.guid),
        'image_guid': str(thumb.image.guid) if thumb.image else None,
        'file_guid': str(thumb.file.guid) if thumb.file else None,
        'size': thumb.size,
        'format': thumb.format,
        'mode': thumb.mode,
        'db_created_at': _dt(thumb.db_created_at),
        'db_updated_at': _dt(thumb.db_updated_at),
        'db_created_by': thumb.db_created_by,
        'db_updated_by': thumb.db_updated_by,
    }


def _read_file_as_base64(file_obj: File) -> str | None:
    """Read a :class:`File` from storage and return as base64 string."""
    try:
        provider = get_storage_provider(file_obj.storage_backend)
        stream = provider.get_file_stream(file_obj.storage_key)
        data = stream.read()
        return base64.b64encode(data).decode('ascii')
    except Exception as exc:
        current_app.logger.warning(
            f'backup_service: could not read file {file_obj.storage_key}: {exc}',
        )
        return None


def _collect_image_media(image: Image | None,
                         files_map: dict[str, dict],
                         images_map: dict[str, dict],
                         thumbs_map: dict[str, dict],
                         media_map: dict[str, str]) -> None:
    """Collect Image, its File, and all Thumbnails into the passed dicts."""
    if image is None:
        return
    img_guid = str(image.guid)
    if img_guid in images_map:
        return  # already collected
    images_map[img_guid] = _image_to_dict(image)
    if image.file:
        f_guid = str(image.file.guid)
        if f_guid not in files_map:
            files_map[f_guid] = _file_to_dict(image.file)
            b64 = _read_file_as_base64(image.file)
            if b64:
                media_map[image.file.storage_key] = b64
    for thumb in image.thumbnails:
        t_guid = str(thumb.guid)
        if t_guid not in thumbs_map:
            thumbs_map[t_guid] = _thumbnail_to_dict(thumb)
            if thumb.file:
                f_guid = str(thumb.file.guid)
                if f_guid not in files_map:
                    files_map[f_guid] = _file_to_dict(thumb.file)
                    b64 = _read_file_as_base64(thumb.file)
                    if b64:
                        media_map[thumb.file.storage_key] = b64


# ---------------------------------------------------------------------------
# Internal helpers — datetime serialization
# ---------------------------------------------------------------------------

def _dt(value: datetime | None) -> str | None:
    """Serialize a datetime to ISO-8601 string, or None."""
    if value is None:
        return None
    return value.isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    """Parse an ISO-8601 string back to a datetime, or return None."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Serializers — one per segment type
# ---------------------------------------------------------------------------

def _serialize_currencies() -> dict[str, Any]:
    """Serialize all Currency records with their flag images."""
    files_map: dict[str, dict] = {}
    images_map: dict[str, dict] = {}
    thumbs_map: dict[str, dict] = {}
    media_map: dict[str, str] = {}

    currencies = Currency.query.all()
    currencies_data = []
    for c in currencies:
        _collect_image_media(c.image, files_map, images_map, thumbs_map, media_map)
        currencies_data.append({
            'guid': str(c.guid),
            'code': c.code,
            'name': c.name,
            'number': c.number,
            'exponent': c.exponent,
            'inCHF': c.inCHF,
            'description': c.description,
            'source': c.source,
            'image_guid': str(c.image.guid) if c.image else None,
            'db_created_at': _dt(c.db_created_at),
            'db_updated_at': _dt(c.db_updated_at),
            'db_created_by': c.db_created_by,
            'db_updated_by': c.db_updated_by,
        })

    return {
        'currencies': currencies_data,
        'files': list(files_map.values()),
        'images': list(images_map.values()),
        'thumbnails': list(thumbs_map.values()),
        'media_files': media_map,
    }


def _serialize_users() -> dict[str, Any]:
    """Serialize all User records with profile pictures, credentials, messages, notifications."""
    files_map: dict[str, dict] = {}
    images_map: dict[str, dict] = {}
    thumbs_map: dict[str, dict] = {}
    media_map: dict[str, str] = {}

    users = User.query.all()
    users_data = []
    for u in users:
        _collect_image_media(u.profile_picture, files_map, images_map, thumbs_map, media_map)
        users_data.append({
            'guid': str(u.guid),
            'username': u.username,
            'email': u.email,
            'password_hash': u.password_hash,
            'is_admin': u.is_admin,
            'locale': u.locale,
            'about_me': u.about_me,
            'profile_picture_guid': str(u.profile_picture.guid) if u.profile_picture else None,
            'db_created_at': _dt(u.db_created_at),
            'db_updated_at': _dt(u.db_updated_at),
            'db_created_by': u.db_created_by,
            'db_updated_by': u.db_updated_by,
        })

    credentials_data = []
    for cred in Credential.query.all():
        credentials_data.append({
            'guid': str(cred.guid),
            'user_guid': str(cred.user.guid) if cred.user else None,
            'credential_id_b64': base64.b64encode(cred.id).decode('ascii') if cred.id else None,
            'public_key_b64': base64.b64encode(cred.public_key).decode('ascii') if cred.public_key else None,
            'sign_count': cred.sign_count,
            'transports': [str(t) for t in cred.transports] if cred.transports else [],
            'db_created_at': _dt(cred.db_created_at),
            'db_updated_at': _dt(cred.db_updated_at),
            'db_created_by': cred.db_created_by,
            'db_updated_by': cred.db_updated_by,
        })

    messages_data = []
    for msg in Message.query.all():
        messages_data.append({
            'guid': str(msg.guid),
            'body': msg.body,
            'timestamp': _dt(msg.timestamp),
            'sender_guid': str(msg.author.guid) if msg.author else None,
            'recipient_guid': str(msg.recipient.guid) if msg.recipient else None,
            'db_created_at': _dt(msg.db_created_at),
            'db_updated_at': _dt(msg.db_updated_at),
            'db_created_by': msg.db_created_by,
            'db_updated_by': msg.db_updated_by,
        })

    notifications_data = []
    for notif in Notification.query.all():
        notifications_data.append({
            'guid': str(notif.guid),
            'name': notif.name,
            'payload_json': notif.payload_json,
            'timestamp': notif.timestamp,  # stored as float (Unix timestamp)
            'user_guid': str(notif.user.guid) if notif.user else None,
            'db_created_at': _dt(notif.db_created_at),
            'db_updated_at': _dt(notif.db_updated_at),
            'db_created_by': notif.db_created_by,
            'db_updated_by': notif.db_updated_by,
        })

    return {
        'users': users_data,
        'credentials': credentials_data,
        'messages': messages_data,
        'notifications': notifications_data,
        'files': list(files_map.values()),
        'images': list(images_map.values()),
        'thumbnails': list(thumbs_map.values()),
        'media_files': media_map,
    }


def _serialize_event(event: Event) -> dict[str, Any]:
    """Serialize a single Event with all dependent objects."""
    files_map: dict[str, dict] = {}
    images_map: dict[str, dict] = {}
    thumbs_map: dict[str, dict] = {}
    media_map: dict[str, str] = {}

    _collect_image_media(event.image, files_map, images_map, thumbs_map, media_map)

    eventusers_data = []
    for eu in event.users:
        _collect_image_media(eu.profile_picture, files_map, images_map, thumbs_map, media_map)
        eventusers_data.append({
            'guid': str(eu.guid),
            'username': eu.username,
            'email': eu.email,
            'weighting': eu.weighting,
            'locale': eu.locale,
            'about_me': eu.about_me,
            'user_guid': str(eu.user.guid) if eu.user else None,
            'profile_picture_guid': str(eu.profile_picture.guid) if eu.profile_picture else None,
            'is_accountant': (event.accountant_id == eu.id) if event.accountant_id else False,
            'db_created_at': _dt(eu.db_created_at),
            'db_updated_at': _dt(eu.db_updated_at),
            'db_created_by': eu.db_created_by,
            'db_updated_by': eu.db_updated_by,
        })

    # Build a guid→EventUser lookup for M2M references
    eu_id_to_guid: dict[int, str] = {eu.id: str(eu.guid) for eu in event.users}

    expenses_data = []
    for exp in event.expenses:
        _collect_image_media(exp.image, files_map, images_map, thumbs_map, media_map)
        affected_guids = [eu_id_to_guid.get(au.id, str(au.guid))
                          for au in exp.affected_users]
        expenses_data.append({
            'guid': str(exp.guid),
            'amount': exp.amount,
            'date': _dt(exp.date),
            'description': exp.description,
            'user_guid': str(exp.user.guid) if exp.user else None,
            'currency_guid': str(exp.currency.guid) if exp.currency else None,
            'image_guid': str(exp.image.guid) if exp.image else None,
            'affected_user_guids': affected_guids,
            'db_created_at': _dt(exp.db_created_at),
            'db_updated_at': _dt(exp.db_updated_at),
            'db_created_by': exp.db_created_by,
            'db_updated_by': exp.db_updated_by,
        })

    settlements_data = []
    for sett in event.settlements:
        _collect_image_media(sett.image, files_map, images_map, thumbs_map, media_map)
        settlements_data.append({
            'guid': str(sett.guid),
            'amount': sett.amount,
            'date': _dt(sett.date),
            'description': sett.description,
            'draft': sett.draft,
            'sender_guid': str(sett.sender.guid) if sett.sender else None,
            'recipient_guid': str(sett.recipient.guid) if sett.recipient else None,
            'currency_guid': str(sett.currency.guid) if sett.currency else None,
            'image_guid': str(sett.image.guid) if sett.image else None,
            'db_created_at': _dt(sett.db_created_at),
            'db_updated_at': _dt(sett.db_updated_at),
            'db_created_by': sett.db_created_by,
            'db_updated_by': sett.db_updated_by,
        })

    posts_data = []
    for post in event.posts:
        posts_data.append({
            'guid': str(post.guid),
            'body': post.body,
            'timestamp': _dt(post.timestamp),
            'author_guid': str(post.author.guid) if post.author else None,
            'db_created_at': _dt(post.db_created_at),
            'db_updated_at': _dt(post.db_updated_at),
            'db_created_by': post.db_created_by,
            'db_updated_by': post.db_updated_by,
        })

    event_currencies_data = []
    for ec in event.eventcurrencies:
        event_currencies_data.append({
            'currency_guid': str(ec.currency.guid) if ec.currency else None,
            'currency_code': ec.currency.code if ec.currency else None,
            'inCHF': ec.inCHF,
        })

    event_data = {
        'guid': str(event.guid),
        'name': event.name,
        'description': event.description,
        'date': _dt(event.date),
        'closed': event.closed,
        'admin_user_guid': str(event.admin.guid) if event.admin else None,
        'base_currency_guid': str(event.base_currency.guid) if event.base_currency else None,
        'base_currency_code': event.base_currency.code if event.base_currency else None,
        'image_guid': str(event.image.guid) if event.image else None,
        'db_created_at': _dt(event.db_created_at),
        'db_updated_at': _dt(event.db_updated_at),
        'db_created_by': event.db_created_by,
        'db_updated_by': event.db_updated_by,
    }

    return {
        'event': event_data,
        'eventusers': eventusers_data,
        'expenses': expenses_data,
        'settlements': settlements_data,
        'posts': posts_data,
        'event_currencies': event_currencies_data,
        'files': list(files_map.values()),
        'images': list(images_map.values()),
        'thumbnails': list(thumbs_map.values()),
        'media_files': media_map,
    }


def _serialize_logs() -> dict[str, Any]:
    """Serialize all Log records (user referenced by GUID)."""
    logs_data = []
    for log in Log.query.all():
        logs_data.append({
            'severity': log.severity,
            'module': log.module,
            'msg_type': log.msg_type,
            'msg': log.msg,
            'trace': log.trace,
            'date': _dt(log.date),
            'user_guid': str(log.user.guid) if log.user else None,
        })
    return {'logs': logs_data}


def _serialize_system() -> dict[str, Any]:
    """Serialize system-level objects (Tasks)."""
    tasks_data = []
    for task in Task.query.all():
        tasks_data.append({
            'guid': str(task.guid),
            'name': task.name,
            'description': task.description,
            'complete': task.complete,
            'user_guid': str(task.user.guid) if task.user else None,
            'db_created_at': _dt(task.db_created_at),
            'db_updated_at': _dt(task.db_updated_at),
        })
    return {'tasks': tasks_data}


# ---------------------------------------------------------------------------
# Segment file I/O helpers
# ---------------------------------------------------------------------------

def _build_segment_json(segment_type: str, segment_key: str | None,
                        objects: dict[str, Any]) -> bytes:
    """Assemble the JSON payload for a segment file and return as UTF-8 bytes."""
    payload = {
        'format_version': BACKUP_FORMAT_VERSION,
        'segment_type': segment_type,
        'segment_key': segment_key,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'objects': objects,
    }
    return json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')


def _compute_checksum(data: bytes) -> str:
    """Return the SHA-256 hex digest of *data*."""
    return hashlib.sha256(data).hexdigest()


def _write_segment(storage_key: str, data: bytes, backend_name: str) -> None:
    """Write *data* to storage under *storage_key*."""
    provider = get_storage_provider(backend_name)
    provider.save(storage_key, io.BytesIO(data), mime_type='application/json')


def _read_segment(storage_key: str, backend_name: str) -> dict[str, Any]:
    """Read a segment JSON file from storage and return parsed dict."""
    provider = get_storage_provider(backend_name)
    stream = provider.get_file_stream(storage_key)
    return json.loads(stream.read().decode('utf-8'))


# ---------------------------------------------------------------------------
# Core public functions
# ---------------------------------------------------------------------------

def create_backup(name: str, segment_types: list[str], user: User,
                  event_guids: list[str] | None = None) -> BackupResult:
    """Create a new BackupSet record and return it (the actual work is done by the RQ task).

    :param name: Human-readable backup name.
    :param segment_types: Which types to include, e.g. ['currencies', 'users', 'events', 'logs', 'system'].
    :param user: The user triggering the backup.
    :param event_guids: If provided, only back up these specific events (partial backup).
    """
    try:
        backend = _backup_backend_name()
        root = _backup_root()
        set_guid = str(uuid.uuid4().hex)
        storage_key = f'{root}/{set_guid}'
        backup_type = 'full' if event_guids is None else 'partial'

        backup_set = BackupSet(
            name=name,
            backup_type=backup_type,
            storage_backend=backend,
            storage_key=storage_key,
            user=user,
            db_created_by=user.username,
        )
        db.session.add(backup_set)

        # Pre-create segment records so the task can track them
        segments_to_create = _plan_segments(segment_types, event_guids)
        for seg_type, seg_key, seg_label in segments_to_create:
            seg_storage_key = _segment_storage_key(storage_key, seg_type, seg_key)
            seg = BackupSegment(
                backup_set=backup_set,
                segment_type=seg_type,
                segment_key=seg_key,
                segment_label=seg_label,
                db_created_by=user.username,
            )
            seg.storage_key = seg_storage_key
            db.session.add(seg)

        backup_set.total_segments = len(segments_to_create)
        db.session.commit()
        return BackupResult(success=True, backup_set=backup_set)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'backup_service.create_backup failed: {exc}', exc_info=True)
        return BackupResult(success=False, error=str(exc))


def _plan_segments(segment_types: list[str],
                   event_guids: list[str] | None) -> list[tuple[str, str | None, str | None]]:
    """Return a list of (type, key, label) tuples for the requested segments."""
    result: list[tuple[str, str | None, str | None]] = []
    for seg_type in segment_types:
        if seg_type == 'events':
            if event_guids:
                for eg in event_guids:
                    event = Event.query.filter(Event.guid == eg).first()
                    label = event.name if event else eg
                    result.append(('event', eg, label))
            else:
                for event in Event.query.all():
                    result.append(('event', str(event.guid), event.name))
        else:
            result.append((seg_type, None, seg_type.capitalize()))
    return result


def _segment_storage_key(set_storage_key: str, seg_type: str,
                         seg_key: str | None) -> str:
    """Compute the storage key for a specific segment file."""
    if seg_key:
        return f'{set_storage_key}/events/{seg_key}.json'
    return f'{set_storage_key}/{seg_type}.json'


def execute_backup_segment(segment: BackupSegment) -> None:
    """Serialize and store a single backup segment. Updates the segment record in-place."""
    seg_type = segment.segment_type
    seg_key = segment.segment_key

    segment.status = 'running'
    db.session.commit()

    try:
        if seg_type == 'currencies':
            objects = _serialize_currencies()
        elif seg_type == 'users':
            objects = _serialize_users()
        elif seg_type == 'event':
            event = Event.query.filter(Event.guid == seg_key).first()
            if event is None:
                raise ValueError(f'Event with guid {seg_key} not found')
            objects = _serialize_event(event)
        elif seg_type == 'logs':
            objects = _serialize_logs()
        elif seg_type == 'system':
            objects = _serialize_system()
        else:
            raise ValueError(f'Unknown segment type: {seg_type}')

        data = _build_segment_json(seg_type, seg_key, objects)
        _write_segment(segment.storage_key, data, segment.backup_set.storage_backend)

        segment.status = 'completed'
        segment.file_size = len(data)
        segment.checksum = _compute_checksum(data)
        # Count primary objects
        primary_counts = {
            'currencies': len(objects.get('currencies', [])),
            'users': len(objects.get('users', [])),
            'event': 1,
            'logs': len(objects.get('logs', [])),
            'system': len(objects.get('tasks', [])),
        }
        segment.record_count = primary_counts.get(seg_type, 0)
        db.session.commit()
    except Exception as exc:
        segment.status = 'failed'
        segment.error_message = str(exc)[:1024]
        db.session.commit()
        raise


def list_backups(page: int) -> PaginatedResult:
    """Return a paginated list of BackupSet records, newest first."""
    from flask import current_app
    per_page = current_app.config.get('ITEMS_PER_PAGE', 10)
    query = BackupSet.query.order_by(BackupSet.db_created_at.desc())
    result = query.paginate(page=page, per_page=per_page, error_out=False)
    return PaginatedResult(
        items=result.items,
        has_next=result.has_next,
        has_prev=result.has_prev,
        next_num=result.next_num,
        prev_num=result.prev_num,
        total=result.total,
    )


def get_backup(guid: str) -> BackupSet | None:
    """Look up a BackupSet by GUID, or return None."""
    return BackupSet.query.filter(BackupSet.guid == guid).first()


def delete_backup(guid: str) -> BackupResult:
    """Delete a BackupSet and all its segment files from storage."""
    backup_set = get_backup(guid)
    if backup_set is None:
        return BackupResult(success=False, error='Backup set not found.')
    try:
        provider = get_storage_provider(backup_set.storage_backend)
        for segment in backup_set.segments:
            if segment.storage_key:
                try:
                    provider.delete(segment.storage_key)
                except Exception as exc:
                    current_app.logger.warning(
                        f'backup_service.delete_backup: could not delete {segment.storage_key}: {exc}',
                    )
        db.session.delete(backup_set)
        db.session.commit()
        return BackupResult(success=True)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'backup_service.delete_backup failed: {exc}', exc_info=True)
        return BackupResult(success=False, error=str(exc))


def export_backup(guid: str) -> ExportResult:
    """Package a BackupSet into a .tar.gz archive and return the bytes."""
    backup_set = get_backup(guid)
    if backup_set is None:
        return ExportResult(success=False, error='Backup set not found.')
    try:
        provider = get_storage_provider(backup_set.storage_backend)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w:gz') as tar:
            # Write a manifest JSON
            manifest = {
                'format_version': BACKUP_FORMAT_VERSION,
                'backup_set_guid': str(backup_set.guid),
                'name': backup_set.name,
                'backup_type': backup_set.backup_type,
                'created_at': _dt(backup_set.db_created_at),
                'segments': [],
            }
            for segment in backup_set.segments:
                manifest['segments'].append({
                    'segment_type': segment.segment_type,
                    'segment_key': segment.segment_key,
                    'segment_label': segment.segment_label,
                    'storage_key': segment.storage_key,
                    'status': segment.status,
                    'record_count': segment.record_count,
                    'file_size': segment.file_size,
                    'checksum': segment.checksum,
                })
                if segment.status == 'completed' and segment.storage_key:
                    try:
                        stream = provider.get_file_stream(segment.storage_key)
                        seg_data = stream.read()
                        archive_name = segment.storage_key.replace('/', '_') + '.json' \
                                       if not segment.storage_key.endswith('.json') \
                                       else segment.storage_key.replace('/', '_')
                        info = tarfile.TarInfo(name=archive_name)
                        info.size = len(seg_data)
                        tar.addfile(info, io.BytesIO(seg_data))
                    except Exception as exc:
                        current_app.logger.warning(
                            f'export_backup: could not add segment {segment.storage_key}: {exc}',
                        )

            manifest_bytes = json.dumps(manifest, ensure_ascii=False,
                                        separators=(',', ':')).encode('utf-8')
            info = tarfile.TarInfo(name='manifest.json')
            info.size = len(manifest_bytes)
            tar.addfile(info, io.BytesIO(manifest_bytes))

        archive_bytes = buf.getvalue()
        safe_name = backup_set.name.replace(' ', '_').replace('/', '_')
        filename = f'backup_{safe_name}_{str(backup_set.guid)[:8]}.tar.gz'
        return ExportResult(success=True, archive_bytes=archive_bytes, filename=filename)
    except Exception as exc:
        current_app.logger.error(f'backup_service.export_backup failed: {exc}', exc_info=True)
        return ExportResult(success=False, error=str(exc))


def import_backup(archive_stream: io.IOBase, user: User) -> ImportResult:
    """Parse an uploaded .tar.gz backup archive and create a BackupSet in the DB.

    The segment files are stored into the configured backup storage backend.
    The actual data restore is a separate step (``run_restore`` task).
    """
    try:
        buf = io.BytesIO(archive_stream.read())
        with tarfile.open(fileobj=buf, mode='r:gz') as tar:
            # Read manifest first
            try:
                manifest_member = tar.getmember('manifest.json')
                manifest_fobj = tar.extractfile(manifest_member)
                manifest = json.loads(manifest_fobj.read().decode('utf-8'))
            except KeyError:
                return ImportResult(success=False, error='Invalid backup archive: manifest.json missing.')

            backend = _backup_backend_name()
            root = _backup_root()
            set_guid = str(uuid.uuid4().hex)
            storage_key = f'{root}/{set_guid}'

            backup_set = BackupSet(
                name=f"Imported: {manifest.get('name', 'unknown')}",
                backup_type=manifest.get('backup_type', 'full'),
                storage_backend=backend,
                storage_key=storage_key,
                user=user,
                db_created_by=user.username,
            )
            db.session.add(backup_set)
            db.session.flush()  # get the id

            provider = get_storage_provider(backend)
            for seg_info in manifest.get('segments', []):
                orig_key = seg_info.get('storage_key', '')
                archive_name = orig_key.replace('/', '_') + '.json' \
                               if not orig_key.endswith('.json') \
                               else orig_key.replace('/', '_')
                new_storage_key = _segment_storage_key(
                    storage_key, seg_info['segment_type'], seg_info.get('segment_key'),
                )
                seg = BackupSegment(
                    backup_set=backup_set,
                    segment_type=seg_info['segment_type'],
                    segment_key=seg_info.get('segment_key'),
                    segment_label=seg_info.get('segment_label'),
                    db_created_by=user.username,
                )
                seg.storage_key = new_storage_key
                seg.record_count = seg_info.get('record_count')
                seg.file_size = seg_info.get('file_size')
                seg.checksum = seg_info.get('checksum')

                # Copy segment data to new storage location
                try:
                    member = tar.getmember(archive_name)
                    fobj = tar.extractfile(member)
                    seg_data = fobj.read()
                    provider.save(new_storage_key, io.BytesIO(seg_data), mime_type='application/json')
                    seg.status = 'completed'
                except KeyError:
                    seg.status = 'failed'
                    seg.error_message = f'Segment file {archive_name} not found in archive.'

                db.session.add(seg)

            backup_set.total_segments = len(manifest.get('segments', []))
            backup_set.completed_segments = sum(
                1 for s in backup_set.segments if s.status == 'completed'
            )
            backup_set.status = 'completed'
            db.session.commit()
            return ImportResult(success=True, backup_set=backup_set)
    except Exception as exc:
        db.session.rollback()
        current_app.logger.error(f'backup_service.import_backup failed: {exc}', exc_info=True)
        return ImportResult(success=False, error=str(exc))


# ---------------------------------------------------------------------------
# Deserializers — used by run_restore task
# ---------------------------------------------------------------------------

def _get_or_create_file(file_dict: dict, media_map: dict[str, str],
                        backend_name: str) -> File | None:
    """Restore a File record and its binary content if not already present."""
    existing = File.query.filter(File.guid == file_dict['guid']).first()
    if existing:
        return existing
    file_obj = File(
        original_filename=file_dict['original_filename'],
        storage_backend=backend_name,
        storage_key=file_dict['storage_key'],
        mime_type=file_dict['mime_type'],
        file_size=file_dict.get('file_size') or 0,
        file_hash=file_dict.get('file_hash'),
        hash_algorithm=file_dict.get('hash_algorithm', 'sha256'),
        db_created_by=file_dict.get('db_created_by', 'restore'),
    )
    file_obj.guid = file_dict['guid']
    file_obj.db_created_at = _parse_dt(file_dict.get('db_created_at'))
    file_obj.db_updated_at = _parse_dt(file_dict.get('db_updated_at'))
    db.session.add(file_obj)

    # Write binary content back to storage
    b64 = media_map.get(file_dict['storage_key'])
    if b64:
        try:
            provider = get_storage_provider(backend_name)
            provider.save(file_dict['storage_key'],
                          io.BytesIO(base64.b64decode(b64)),
                          mime_type=file_dict.get('mime_type'))
        except Exception as exc:
            current_app.logger.warning(
                f'restore: could not write file {file_dict["storage_key"]}: {exc}',
            )
    return file_obj


def _get_or_create_image(image_dict: dict, files_by_guid: dict[str, dict],
                         media_map: dict[str, str], backend_name: str) -> Image | None:
    """Restore an Image record if not already present."""
    existing = Image.query.filter(Image.guid == image_dict['guid']).first()
    if existing:
        return existing
    file_dict = files_by_guid.get(image_dict.get('file_guid', ''))
    file_obj = None
    if file_dict:
        file_obj = _get_or_create_file(file_dict, media_map, backend_name)

    image = Image(
        file_obj=file_obj,
        is_vector=image_dict.get('is_vector', False),
        width=image_dict.get('width') or 0,
        height=image_dict.get('height') or 0,
        db_created_by=image_dict.get('db_created_by', 'restore'),
    )
    image.guid = image_dict['guid']
    image.rotate = image_dict.get('rotate')
    image.format = image_dict.get('format')
    image.mode = image_dict.get('mode')
    image.description = image_dict.get('description')
    image.db_created_at = _parse_dt(image_dict.get('db_created_at'))
    image.db_updated_at = _parse_dt(image_dict.get('db_updated_at'))
    db.session.add(image)
    return image


def _restore_media(objects: dict, backend_name: str,
                   strategy: str) -> tuple[dict[str, File], dict[str, Image]]:
    """Restore File and Image records from a segment's object dict.

    Returns (files_by_guid, images_by_guid) dicts for cross-referencing.
    """
    media_map: dict[str, str] = objects.get('media_files', {})
    files_by_guid: dict[str, dict] = {f['guid']: f for f in objects.get('files', [])}
    images_by_guid: dict[str, dict] = {i['guid']: i for i in objects.get('images', [])}

    restored_files: dict[str, File] = {}
    restored_images: dict[str, Image] = {}

    for f_dict in objects.get('files', []):
        restored_files[f_dict['guid']] = _get_or_create_file(f_dict, media_map, backend_name)

    for i_dict in objects.get('images', []):
        restored_images[i_dict['guid']] = _get_or_create_image(
            i_dict, files_by_guid, media_map, backend_name,
        )

    for t_dict in objects.get('thumbnails', []):
        existing = Thumbnail.query.filter(Thumbnail.guid == t_dict['guid']).first()
        if existing:
            continue
        image = restored_images.get(t_dict.get('image_guid', ''))
        file_obj = restored_files.get(t_dict.get('file_guid', ''))
        if image and file_obj:
            thumb = Thumbnail(image=image, size=t_dict.get('size', 0), file_obj=file_obj,
                              db_created_by=t_dict.get('db_created_by', 'restore'))
            thumb.guid = t_dict['guid']
            thumb.format = t_dict.get('format')
            thumb.mode = t_dict.get('mode')
            thumb.db_created_at = _parse_dt(t_dict.get('db_created_at'))
            thumb.db_updated_at = _parse_dt(t_dict.get('db_updated_at'))
            db.session.add(thumb)

    db.session.flush()
    return restored_files, restored_images


def restore_currencies(objects: dict, strategy: str,
                       backend_name: str,
                       currency_remap: dict[str, str] | None = None) -> dict[str, int]:
    """Restore currencies from a parsed segment objects dict.

    *currency_remap* is an optional dict populated in-place that maps each
    backup GUID to the DB GUID of the resolved currency.  When a currency is
    reconciled by code (same code, different GUID), the entry records the
    translation so that restore_event can locate the correct row.
    """
    if currency_remap is None:
        currency_remap = {}
    _restore_media(objects, backend_name, strategy)
    db.session.flush()

    images_by_guid: dict[str, Image] = {
        img.guid if isinstance(img.guid, str) else str(img.guid):
        img for img in Image.query.all()
    }

    restored = 0
    skipped = 0
    for c_dict in objects.get('currencies', []):
        backup_guid = c_dict.get('guid', '')
        existing = Currency.query.filter(or_(
            Currency.guid == backup_guid,
            Currency.code == c_dict['code'],
        )).first()
        if existing:
            # Always record the remap regardless of strategy.  If this currency
            # was reconciled by code (DB has same code but different GUID), the
            # map lets restore_event translate the stale backup GUID to the DB GUID.
            currency_remap[backup_guid] = str(existing.guid)
            if strategy == 'overwrite':
                existing.code = c_dict['code']
                existing.name = c_dict['name']
                existing.number = c_dict.get('number')
                existing.exponent = c_dict.get('exponent')
                existing.inCHF = c_dict.get('inCHF')
                existing.description = c_dict.get('description')
                existing.source = c_dict.get('source')
                restored += 1
            else:
                skipped += 1
            continue

        img = images_by_guid.get(c_dict.get('image_guid', ''))
        currency = Currency(
            code=c_dict['code'],
            name=c_dict['name'],
            number=c_dict.get('number') or 0,
            exponent=c_dict.get('exponent') or 2,
            inCHF=c_dict.get('inCHF') or 1.0,
            description=c_dict.get('description', ''),
            db_created_by=c_dict.get('db_created_by', 'restore'),
        )
        currency.guid = backup_guid
        currency.source = c_dict.get('source')
        currency.image = img
        currency.db_created_at = _parse_dt(c_dict.get('db_created_at'))
        currency.db_updated_at = _parse_dt(c_dict.get('db_updated_at'))
        db.session.add(currency)
        # For newly created rows the DB GUID equals the backup GUID (identity mapping).
        currency_remap[backup_guid] = backup_guid
        restored += 1

    db.session.flush()
    return {'restored': restored, 'skipped': skipped}


def restore_users(objects: dict, strategy: str, backend_name: str,
                  user_remap: dict[str, str] | None = None) -> dict[str, int]:
    """Restore users from a parsed segment objects dict.

    *user_remap* is an optional dict populated in-place that maps each backup
    GUID to the DB GUID of the resolved User row, enabling restore_event to
    translate stale GUIDs when a user was reconciled by email / username.
    """
    if user_remap is None:
        user_remap = {}
    _restore_media(objects, backend_name, strategy)
    db.session.flush()

    images_by_guid: dict[str, Image] = {
        str(img.guid): img for img in Image.query.all()
    }

    restored = 0
    skipped = 0
    for u_dict in objects.get('users', []):
        backup_guid = u_dict.get('guid', '')
        existing = User.query.filter(or_(
            User.guid == backup_guid,
            User.email == (u_dict.get('email') or '').lower(),
            User.username == u_dict['username'],
        )).first()
        if existing:
            # Record the remap so restore_event can translate stale backup GUIDs
            # (e.g. after flask dbinit re-seeds users with fresh GUIDs).
            user_remap[backup_guid] = str(existing.guid)
            if strategy == 'overwrite':
                existing.username = u_dict['username']
                existing.email = u_dict['email']
                existing.password_hash = u_dict.get('password_hash')
                existing.is_admin = u_dict.get('is_admin', False)
                existing.locale = u_dict.get('locale')
                existing.about_me = u_dict.get('about_me')
                existing.profile_picture = images_by_guid.get(u_dict.get('profile_picture_guid', ''))
                restored += 1
            else:
                skipped += 1
            continue

        user = User(username=u_dict['username'], email=u_dict['email'],
                    locale=u_dict.get('locale') or 'en',
                    about_me=u_dict.get('about_me') or '',
                    db_created_by=u_dict.get('db_created_by', 'restore'))
        user.guid = backup_guid
        user.password_hash = u_dict.get('password_hash')
        user.is_admin = u_dict.get('is_admin', False)
        user.locale = u_dict.get('locale')
        user.about_me = u_dict.get('about_me')
        user.profile_picture = images_by_guid.get(u_dict.get('profile_picture_guid', ''))
        user.db_created_at = _parse_dt(u_dict.get('db_created_at'))
        user.db_updated_at = _parse_dt(u_dict.get('db_updated_at'))
        db.session.add(user)
        user_remap[backup_guid] = backup_guid
        restored += 1

    db.session.flush()
    return {'users_restored': restored, 'users_skipped': skipped}


def restore_event(objects: dict, strategy: str, backend_name: str,
                  guid_remap: dict[str, dict[str, str]] | None = None) -> dict[str, int]:
    """Restore a single event and all its dependents from a parsed segment dict.

    *guid_remap* is an optional nested dict produced by apply_restore::

        {'currency': {backup_guid: db_guid, ...},
         'user':     {backup_guid: db_guid, ...}}

    When currencies or users were reconciled by natural key (code / email) their
    DB GUIDs differ from the backup GUIDs.  The remap lets us locate the correct
    row even for existing backups that only carry GUIDs.  As a second fallback,
    the event payload now also stores currency codes so event-only restores of
    recent backups can resolve currencies without the currencies segment.
    """
    if guid_remap is None:
        guid_remap = {}
    currency_remap: dict[str, str] = guid_remap.get('currency', {})
    user_remap: dict[str, str] = guid_remap.get('user', {})

    _restore_media(objects, backend_name, strategy)
    db.session.flush()

    images_by_guid: dict[str, Image] = {str(img.guid): img for img in Image.query.all()}
    currencies_by_guid: dict[str, Currency] = {
        str(c.guid): c for c in Currency.query.all()
    }
    currencies_by_code: dict[str, Currency] = {c.code: c for c in Currency.query.all()}
    users_by_guid: dict[str, User] = {str(u.guid): u for u in User.query.all()}

    def _resolve_currency(guid: str | None, code: str | None = None) -> Currency | None:
        """Resolve a currency with GUID-remap and code fallback."""
        if not guid:
            return currencies_by_code.get(code) if code else None
        return (
            currencies_by_guid.get(guid)
            or currencies_by_guid.get(currency_remap.get(guid, ''))
            or (currencies_by_code.get(code) if code else None)
        )

    def _resolve_user(guid: str | None) -> User | None:
        """Resolve a user with GUID-remap fallback."""
        if not guid:
            return None
        return users_by_guid.get(guid) or users_by_guid.get(user_remap.get(guid, ''))

    event_dict = objects.get('event', {})
    existing_event = Event.query.filter(Event.guid == event_dict.get('guid')).first()

    if existing_event and strategy == 'skip':
        return {'event_skipped': 1}

    if existing_event is None:
        base_currency = _resolve_currency(
            event_dict.get('base_currency_guid'),
            event_dict.get('base_currency_code'),
        )
        admin_user = _resolve_user(event_dict.get('admin_user_guid'))
        event = Event(
            name=event_dict['name'],
            date=_parse_dt(event_dict.get('date')) or datetime.now(timezone.utc),
            admin=admin_user,
            base_currency=base_currency,
            currencies=[base_currency] if base_currency else [],
            exchange_fee=event_dict.get('exchange_fee') or 0.0,
            fileshare_link=event_dict.get('fileshare_link') or '',
            closed=event_dict.get('closed', False),
            description=event_dict.get('description') or '',
            db_created_by=event_dict.get('db_created_by', 'restore'),
        )
        event.guid = event_dict['guid']
        event.image = images_by_guid.get(event_dict.get('image_guid', ''))
        event.db_created_at = _parse_dt(event_dict.get('db_created_at'))
        event.db_updated_at = _parse_dt(event_dict.get('db_updated_at'))
        db.session.add(event)
        db.session.flush()
    else:
        event = existing_event
        event.name = event_dict['name']
        event.description = event_dict.get('description')
        event.closed = event_dict.get('closed', False)

    # Restore EventUsers
    eu_guid_to_obj: dict[str, EventUser] = {}
    for eu_dict in objects.get('eventusers', []):
        existing_eu = EventUser.query.filter(EventUser.guid == eu_dict['guid']).first()
        if existing_eu:
            eu_guid_to_obj[eu_dict['guid']] = existing_eu
            continue
        linked_user = _resolve_user(eu_dict.get('user_guid'))
        eu = EventUser(
            username=eu_dict['username'],
            email=eu_dict['email'],
            weighting=eu_dict.get('weighting', 1.0),
            locale=eu_dict.get('locale', 'en'),
            about_me=eu_dict.get('about_me', ''),
            user_id=linked_user.id if linked_user else None,
            db_created_by=eu_dict.get('db_created_by', 'restore'),
        )
        eu.guid = eu_dict['guid']
        eu.event = event
        eu.profile_picture = images_by_guid.get(eu_dict.get('profile_picture_guid', ''))
        eu.db_created_at = _parse_dt(eu_dict.get('db_created_at'))
        eu.db_updated_at = _parse_dt(eu_dict.get('db_updated_at'))
        db.session.add(eu)
        eu_guid_to_obj[eu_dict['guid']] = eu

    db.session.flush()

    # Set accountant — use direct scalar FK assignment to avoid ORM circular
    # dependency: events.accountant_id ↔ eventusers.event_id mutual FK pair
    # would trigger CircularDependencyError if the ORM relationship is used
    # when both Event and EventUser are new in the same flush context.
    for eu_dict in objects.get('eventusers', []):
        if eu_dict.get('is_accountant'):
            eu_obj = eu_guid_to_obj.get(eu_dict['guid'])
            if eu_obj:
                event.accountant_id = eu_obj.id

    # Restore EventCurrencies
    for ec_dict in objects.get('event_currencies', []):
        currency = _resolve_currency(
            ec_dict.get('currency_guid'),
            ec_dict.get('currency_code'),
        )
        if currency:
            existing_ec = EventCurrency.query.filter_by(
                event_id=event.id, currency_id=currency.id,
            ).first()
            if not existing_ec:
                ec = EventCurrency(currency=currency)
                ec.event = event
                ec.inCHF = ec_dict.get('inCHF')
                db.session.add(ec)

    db.session.flush()

    # Restore Expenses
    expenses_restored = 0
    for exp_dict in objects.get('expenses', []):
        if Expense.query.filter(Expense.guid == exp_dict['guid']).first():
            continue
        user_obj = eu_guid_to_obj.get(exp_dict.get('user_guid', ''))
        currency = _resolve_currency(exp_dict.get('currency_guid'))
        expense = Expense(
            user=user_obj,
            event=event,
            currency=currency,
            amount=exp_dict.get('amount', 0.0),
            affected_users=[],
            date=_parse_dt(exp_dict.get('date')) or datetime.now(timezone.utc),
            description=exp_dict.get('description') or '',
            db_created_by=exp_dict.get('db_created_by', 'restore'),
        )
        expense.guid = exp_dict['guid']
        expense.image = images_by_guid.get(exp_dict.get('image_guid', ''))
        expense.db_created_at = _parse_dt(exp_dict.get('db_created_at'))
        expense.db_updated_at = _parse_dt(exp_dict.get('db_updated_at'))
        db.session.add(expense)
        db.session.flush()
        for affected_guid in exp_dict.get('affected_user_guids', []):
            affected_eu = eu_guid_to_obj.get(affected_guid)
            if affected_eu:
                expense.affected_users.append(affected_eu)
        expenses_restored += 1

    # Restore Settlements
    settlements_restored = 0
    for sett_dict in objects.get('settlements', []):
        if Settlement.query.filter(Settlement.guid == sett_dict['guid']).first():
            continue
        sender = eu_guid_to_obj.get(sett_dict.get('sender_guid', ''))
        recipient = eu_guid_to_obj.get(sett_dict.get('recipient_guid', ''))
        currency = _resolve_currency(sett_dict.get('currency_guid'))
        sett = Settlement(
            amount=sett_dict.get('amount', 0.0),
            date=_parse_dt(sett_dict.get('date')) or datetime.now(timezone.utc),
            sender=sender,
            recipient=recipient,
            event=event,
            currency=currency,
            draft=sett_dict.get('draft', False),
            description=sett_dict.get('description') or '',
            db_created_by=sett_dict.get('db_created_by', 'restore'),
        )
        sett.guid = sett_dict['guid']
        sett.image = images_by_guid.get(sett_dict.get('image_guid', ''))
        sett.db_created_at = _parse_dt(sett_dict.get('db_created_at'))
        sett.db_updated_at = _parse_dt(sett_dict.get('db_updated_at'))
        db.session.add(sett)
        settlements_restored += 1

    # Restore Posts
    posts_restored = 0
    for post_dict in objects.get('posts', []):
        if Post.query.filter(Post.guid == post_dict['guid']).first():
            continue
        author = eu_guid_to_obj.get(post_dict.get('author_guid', ''))
        post = Post(
            body=post_dict.get('body', ''),
            timestamp=_parse_dt(post_dict.get('timestamp')) or datetime.now(timezone.utc),
            author=author,
            event=event,
            db_created_by=post_dict.get('db_created_by', 'restore'),
        )
        post.guid = post_dict['guid']
        post.db_created_at = _parse_dt(post_dict.get('db_created_at'))
        post.db_updated_at = _parse_dt(post_dict.get('db_updated_at'))
        db.session.add(post)
        posts_restored += 1

    db.session.flush()
    return {
        'eventusers': len(eu_guid_to_obj),
        'expenses': expenses_restored,
        'settlements': settlements_restored,
        'posts': posts_restored,
    }


def restore_logs(objects: dict, strategy: str,
                 user_remap: dict[str, str] | None = None) -> dict[str, int]:
    """Restore Log records from a parsed segment dict."""
    if user_remap is None:
        user_remap = {}
    users_by_guid: dict[str, User] = {str(u.guid): u for u in User.query.all()}

    def _resolve_user(guid: str | None) -> User | None:
        if not guid:
            return None
        return users_by_guid.get(guid) or users_by_guid.get(user_remap.get(guid, ''))

    restored = 0
    for log_dict in objects.get('logs', []):
        user = _resolve_user(log_dict.get('user_guid'))
        log = Log(
            severity=log_dict.get('severity', 'INFO'),
            module=log_dict.get('module', ''),
            msg_type=log_dict.get('msg_type', ''),
            msg=log_dict.get('msg', ''),
            user=user,
            trace=log_dict.get('trace'),
        )
        log.date = _parse_dt(log_dict.get('date'))
        db.session.add(log)
        restored += 1
    db.session.flush()
    return {'logs_restored': restored}


def apply_restore(backup_set: BackupSet, strategy: str) -> dict[str, Any]:
    """Apply all segments of *backup_set* in dependency order.

    Restore order: currencies → users → events → logs → system.
    Returns a dict of per-segment restore counts.

    A shared *guid_remap* table is built as currencies and users are restored.
    It maps backup GUIDs to DB GUIDs for rows that were reconciled by natural
    key (currency code / user email+username).  restore_event and restore_logs
    consume this table so that cross-references in event payloads resolve
    correctly even after flask dbinit re-seeds with fresh GUIDs.
    """
    # Sort segments: currencies first, then users, then events, then logs, then system
    ORDER = ['currencies', 'users', 'event', 'logs', 'system']
    segments = sorted(
        backup_set.segments,
        key=lambda s: ORDER.index(s.segment_type) if s.segment_type in ORDER else 99,
    )

    # Shared GUID translation tables populated by restore_currencies / restore_users.
    guid_remap: dict[str, dict[str, str]] = {'currency': {}, 'user': {}}

    totals: dict[str, Any] = {}
    for segment in segments:
        if segment.status != 'completed':
            continue
        try:
            payload = _read_segment(segment.storage_key, backup_set.storage_backend)
            objects = payload.get('objects', {})
            backend = backup_set.storage_backend
            if segment.segment_type == 'currencies':
                counts = restore_currencies(objects, strategy, backend,
                                            guid_remap['currency'])
            elif segment.segment_type == 'users':
                counts = restore_users(objects, strategy, backend,
                                       guid_remap['user'])
            elif segment.segment_type == 'event':
                counts = restore_event(objects, strategy, backend, guid_remap)
            elif segment.segment_type == 'logs':
                counts = restore_logs(objects, strategy, guid_remap['user'])
            else:
                counts = {}
            totals[f'{segment.segment_type}:{segment.segment_key or ""}'] = counts
            db.session.commit()
        except Exception as exc:
            db.session.rollback()
            current_app.logger.error(
                f'apply_restore: error restoring segment {segment}: {exc}', exc_info=True,
            )
            totals[f'{segment.segment_type}:{segment.segment_key or ""}'] = {'error': str(exc)}

    return totals


def enforce_retention(max_count: int) -> int:
    """Delete the oldest scheduled backup sets exceeding *max_count*.

    Returns the number of backup sets deleted.
    """
    sets = BackupSet.query.filter(
        BackupSet.status == 'completed',
    ).order_by(BackupSet.db_created_at.asc()).all()

    deleted = 0
    while len(sets) > max_count:
        oldest = sets.pop(0)
        result = delete_backup(str(oldest.guid))
        if result.success:
            deleted += 1
        else:
            current_app.logger.warning(
                f'enforce_retention: could not delete {oldest.guid}: {result.error}',
            )
    return deleted
