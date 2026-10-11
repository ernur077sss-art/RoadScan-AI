from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID
import hashlib
import hmac
import json
import secrets
import tempfile
import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File, Header, Query
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy import select, text, func, bindparam, BigInteger
from sqlalchemy.orm import Session as DbSession
from .body_limit import BodyLimitMiddleware, BodyTooLarge
from .config import Settings
from .db import connect, initialize, lock_key
from .models import User, Challenge, Session, Media, Observation, Incident, Audit, Outbox, now, uid
from .schemas import PhoneRequest, VerifyRequest, PasswordLogin, PasswordRegistration, ReportRequest, Decision, Clarification, RoleRequest, LocationUpdate
from .security import normalize_phone, digest, cipher, limit
from .passwords import hash_password, verify_password, validate_role_password
from .storage import Storage, validate_media


def get_db(request: Request):
    with request.app.state.sessions() as db:
        if db.bind.dialect.name == 'sqlite' and request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            db.execute(text('BEGIN IMMEDIATE'))
        try:
            yield db
        finally:
            db.rollback()


def current_user(request: Request, db: DbSession = Depends(get_db)):
    token = request.cookies.get('roadscan_session', '')
    session = db.get(Session, digest(request.app.state.settings, 'session:' + token)) if token else None
    if not session or session.expires_at <= now():
        raise HTTPException(401, 'Войдите по номеру телефона')
    user = db.get(User, session.user_id)
    if not user:
        raise HTTPException(401, 'Сессия завершена')
    try:
        validate_role_password(user.password_hash, user.role)
    except ValueError as exc:
        raise HTTPException(403, str(exc)) from None
    return user


def inspector(user: User = Depends(current_user)):
    if user.role not in {'inspector', 'admin'}:
        raise HTTPException(403, 'Доступ только для инспектора')
    return user


def accessible(db, report_id, user, lock=False):
    q = select(Observation).where(Observation.id == str(report_id))
    row = db.scalar(q.with_for_update() if lock else q)
    if not row or (user.role == 'citizen' and row.author_id != user.id):
        raise HTTPException(404, 'Обращение не найдено')
    return row


def audit(db, user, row, action, note, details=None):
    db.add(Audit(report_id=row.id if row else None, actor_id=user.id if user else None, action=action, note=note, details=json.dumps(details or {}, ensure_ascii=False)))


def report_json(db, row, detail=False):
    incident = db.get(Incident, row.incident_id) if row.incident_id else None
    outbox = db.scalar(select(Outbox).where(Outbox.incident_id == row.incident_id)) if incident else None
    media = db.scalars(select(Media).where(Media.report_id == row.id).order_by(Media.created_at, Media.id)).all()
    data = {k: getattr(row, k) for k in ['id', 'category', 'description', 'address', 'latitude', 'longitude', 'location_source', 'device_accuracy', 'status', 'incident_id', 'response', 'received_at', 'updated_at', 'version']}
    data['number'] = 'НК-' + row.id[:8].upper()
    data['media'] = [{'id': m.id, 'kind': m.kind, 'url': '/api/media/' + m.id, 'size': m.size} for m in media]
    data['incident'] = None if not incident else {'id': incident.id, 'latitude': incident.latitude, 'longitude': incident.longitude, 'location_verified': incident.location_verified, 'first_received_at': incident.first_received_at, 'version': incident.version}
    data['integration'] = None if not outbox else {'status': outbox.status, 'external_id': outbox.external_id, 'attempts': outbox.attempts, 'last_error': outbox.last_error}
    if detail:
        events = db.scalars(select(Audit).where(Audit.report_id == row.id).order_by(Audit.created_at, Audit.id)).all()
        data['history'] = [{'action': a.action, 'note': a.note, 'created_at': a.created_at} for a in events]
    return data


def create_app(settings=None):
    settings = (settings or Settings()).prepare()
    engine, sessions = connect(settings)

    @asynccontextmanager
    async def lifespan(app):
        if settings.environment != 'production':
            initialize(engine)
        yield
        engine.dispose()

    app = FastAPI(title='Народный контроль · RoadScan API', version='0.1.0', lifespan=lifespan)
    app.state.settings, app.state.sessions = settings, sessions
    app.state.engine = engine
    app.state.storage = Storage(settings)

    @app.middleware('http')
    async def guards(request, call_next):
        if request.method not in {'GET', 'HEAD', 'OPTIONS'}:
            if request.headers.get('origin') != settings.origin or request.headers.get('x-roadscan-request') != '1':
                return JSONResponse({'detail': 'Недопустимый источник запроса'}, status_code=403)
        length = request.headers.get('content-length', '0')
        if request.method == 'POST' and request.url.path == '/api/media' and (not length.isdigit() or int(length) == 0):
            return JSONResponse({'detail': 'Для загрузки требуется Content-Length'}, status_code=411)
        if length.isdigit() and int(length) > settings.max_upload + 1024 * 1024:
            return JSONResponse({'detail': 'Файл слишком большой (максимум 25 MB)'}, status_code=413)
        response = await call_next(request)
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'same-origin'
        return response

    app.add_middleware(BodyLimitMiddleware, max_bytes=settings.max_upload + 1024 * 1024)

    @app.exception_handler(BodyTooLarge)
    async def oversized_body(request, exc):
        return JSONResponse({'detail': 'Размер запроса превышает лимит 26 MB'}, status_code=413, headers={'Cache-Control': 'no-store'})

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request, exc):
        # Do not echo passwords, OTPs, phones, or rejected request bodies.
        errors = [{'field': '.'.join(str(x) for x in e['loc'][1:]), 'message': e['msg']} for e in exc.errors()]
        return JSONResponse({'detail': 'Проверьте заполнение полей', 'errors': errors}, status_code=422)

    @app.get('/api/health')
    def health(db=Depends(get_db)):
        db.execute(text('SELECT 1'))
        return {'status': 'ok', 'environment': settings.environment, 'auth_mode': settings.auth_mode, 'sms': settings.sms_mode if settings.auth_mode == 'otp' else 'disabled', 'integration_109': settings.integration_mode, 'database': engine.dialect.name}

    def require_auth_mode(mode):
        if settings.auth_mode != mode:
            raise HTTPException(404, 'Этот способ входа отключён')

    def start_session(user, request, response, db):
        # Rotate the current session instead of retaining a fixed login cookie.
        previous = request.cookies.get('roadscan_session')
        if previous:
            old = db.get(Session, digest(settings, 'session:' + previous))
            if old:
                db.delete(old)
        token = secrets.token_urlsafe(48)
        db.add(Session(token_hash=digest(settings, 'session:' + token), user_id=user.id, expires_at=now() + 30 * 86400))
        db.commit()
        response.set_cookie('roadscan_session', token, max_age=30 * 86400, httponly=True, secure=settings.environment == 'production' or settings.origin.startswith('https://'), samesite='lax', path='/')
        return {'id': user.id, 'role': user.role}

    def password_limits(phone, request, db, registering=False):
        ip = request.client.host if request.client else 'unknown'
        limit(db, settings, 'password-ip:' + ip, 30, 900)
        limit(db, settings, 'password-phone:' + phone, 5, 900)
        limit(db, settings, 'password-phone-day:' + phone, 20, 86400)
        if registering:
            limit(db, settings, 'registration-ip:' + ip, 10, 3600)
        # Persist unsuccessful attempts as well; release locks before scrypt.
        db.commit()

    @app.post('/api/auth/register', status_code=201)
    def register(body: PasswordRegistration, request: Request, response: Response, db=Depends(get_db)):
        require_auth_mode('password')
        phone = normalize_phone(body.phone)
        password_limits(phone, request, db, registering=True)
        encoded = hash_password(body.password)
        phone_key = digest(settings, 'phone:' + phone)
        if db.bind.dialect.name == 'sqlite':
            db.execute(text('BEGIN IMMEDIATE'))
        lock_key(db, 'phone:' + phone_key)
        if db.scalar(select(User).where(User.phone_key == phone_key)):
            # Never attach a new password to an account on a claimed phone alone.
            raise HTTPException(409, 'Не удалось создать аккаунт с этим номером. Если он уже зарегистрирован, используйте вход.')
        user = User(phone_key=phone_key, phone_encrypted=cipher(settings).encrypt(phone.encode()).decode(), password_hash=encoded, phone_verified=False, consent_version='password-pilot-v1')
        db.add(user)
        db.flush()
        audit(db, user, None, 'registered', 'Создан аккаунт без подтверждения номера телефона.')
        return start_session(user, request, response, db)

    @app.post('/api/auth/login')
    def password_login(body: PasswordLogin, request: Request, response: Response, db=Depends(get_db)):
        require_auth_mode('password')
        phone = normalize_phone(body.phone)
        password_limits(phone, request, db)
        user = db.scalar(select(User).where(User.phone_key == digest(settings, 'phone:' + phone)))
        if not verify_password(body.password, user.password_hash if user else None):
            raise HTTPException(401, 'Неверный номер телефона или пароль')
        try:
            validate_role_password(user.password_hash, user.role)
        except ValueError as exc:
            raise HTTPException(403, str(exc)) from None
        return start_session(user, request, response, db)

    @app.post('/api/auth/request')
    def request_otp(body: PhoneRequest, request: Request, db=Depends(get_db)):
        require_auth_mode('otp')
        phone = normalize_phone(body.phone)
        limit(db, settings, 'sms-ip:' + (request.client.host if request.client else 'unknown'), 15, 600)
        limit(db, settings, 'sms-phone:' + phone, 1, 60)
        limit(db, settings, 'sms-day:' + phone, 10, 86400)
        phone_key = digest(settings, 'phone:' + phone)
        lock_key(db, 'phone:' + phone_key)
        for previous in db.scalars(select(Challenge).where(Challenge.phone_key == phone_key, Challenge.used.is_(False))):
            previous.used = True
        challenge_id, code = uid(), f'{secrets.randbelow(1000000):06d}'
        item = Challenge(id=challenge_id, phone_key=phone_key, phone_encrypted=cipher(settings).encrypt(phone.encode()).decode(), code_hash=digest(settings, challenge_id + ':' + code), expires_at=now() + 300)
        db.add(item)
        db.commit()
        if settings.sms_mode == 'bridge':
            try:
                r = httpx.post(settings.sms_url, json={'phone': phone, 'text': f'Народный контроль: код {code}. Никому не сообщайте.', 'request_id': challenge_id}, headers={'Authorization': 'Bearer ' + settings.sms_token}, timeout=10)
                r.raise_for_status()
                receipt = r.json()
                if not isinstance(receipt, dict) or receipt.get('accepted') is not True:
                    raise ValueError('Provider did not accept message')
            except (httpx.HTTPError, ValueError):
                item.used = True
                db.commit()
                raise HTTPException(503, 'Не удалось отправить SMS. Попробуйте через минуту.')
        data = {'challenge_id': challenge_id, 'expires_in': 300, 'mode': settings.sms_mode}
        if settings.sms_mode == 'development' and settings.environment != 'production':
            data['development_code'] = code
        return data

    @app.post('/api/auth/verify')
    def verify(body: VerifyRequest, request: Request, response: Response, db=Depends(get_db)):
        require_auth_mode('otp')
        challenge = db.scalar(select(Challenge).where(Challenge.id == str(body.challenge_id)).with_for_update())
        if not challenge or challenge.used or challenge.expires_at <= now() or challenge.attempts >= 5:
            raise HTTPException(400, 'Код недействителен. Запросите новый.')
        challenge.attempts += 1
        if not hmac.compare_digest(challenge.code_hash, digest(settings, challenge.id + ':' + body.code)):
            db.commit()
            raise HTTPException(400, 'Неверный код')
        challenge.used = True
        lock_key(db, 'phone:' + challenge.phone_key)
        user = db.scalar(select(User).where(User.phone_key == challenge.phone_key))
        if not user:
            user = User(phone_key=challenge.phone_key, phone_encrypted=challenge.phone_encrypted)
            db.add(user)
            db.flush()
        if settings.sms_mode == 'bridge':
            user.phone_verified = True
        return start_session(user, request, response, db)

    @app.get('/api/auth/me')
    def me(user=Depends(current_user)):
        phone = cipher(settings).decrypt(user.phone_encrypted.encode()).decode()
        return {'id': user.id, 'role': user.role, 'phone': phone, 'phone_verified': user.phone_verified, 'consent_version': user.consent_version}

    @app.post('/api/auth/logout')
    def logout(request: Request, response: Response, user=Depends(current_user), db=Depends(get_db)):
        session = db.get(Session, digest(settings, 'session:' + request.cookies['roadscan_session']))
        db.delete(session)
        db.commit()
        response.delete_cookie('roadscan_session', path='/')
        return {'ok': True}

    @app.post('/api/media')
    def upload(file: UploadFile = File(...), x_upload_id: UUID = Header(...), user=Depends(current_user), db=Depends(get_db)):
        lock_key(db, 'upload:' + user.id + str(x_upload_id))
        existing = db.scalar(select(Media).where(Media.owner_id == user.id, Media.upload_key == str(x_upload_id)))
        with tempfile.NamedTemporaryFile(dir=settings.data_dir, prefix='upload-', delete=False) as temp:
            path = Path(temp.name)
            total, raw_hash = 0, hashlib.sha256()
            try:
                while chunk := file.file.read(1024 * 1024):
                    total += len(chunk)
                    if total > settings.max_upload:
                        raise HTTPException(413, 'Файл слишком большой (максимум 25 MB)')
                    raw_hash.update(chunk)
                    temp.write(chunk)
                temp.close()
                sha = raw_hash.hexdigest()
                if existing:
                    if existing.sha256 != sha:
                        raise HTTPException(409, 'Идентификатор загрузки уже использован для другого файла')
                    return {'id': existing.id, 'kind': existing.kind, 'url': '/api/media/' + existing.id}
                limit(db, settings, 'uploads:' + user.id, 30, 3600)
                kind, mime = validate_media(path, file.content_type or '')
                media = Media(id=uid(), owner_id=user.id, upload_key=str(x_upload_id), kind=kind, mime=mime, sha256=sha, size=path.stat().st_size)
                app.state.storage.put(media.id, path, mime)
                try:
                    db.add(media)
                    db.commit()
                except Exception:
                    db.rollback()
                    app.state.storage.delete(media.id)
                    raise
                return {'id': media.id, 'kind': kind, 'url': '/api/media/' + media.id}
            finally:
                path.unlink(missing_ok=True)
                file.file.close()

    @app.get('/api/media/{media_id}')
    def read_media(media_id: UUID, request: Request, user=Depends(current_user), db=Depends(get_db)):
        media = db.get(Media, str(media_id))
        if not media or (media.owner_id != user.id and (user.role == 'citizen' or media.report_id is None)):
            raise HTTPException(404, 'Файл не найден')
        if settings.storage == 's3':
            import re
            from botocore.exceptions import ClientError
            args = {'Bucket': settings.s3_bucket, 'Key': media.id}
            range_header = request.headers.get('range')
            if range_header:
                if not re.fullmatch(r'bytes=\d*-\d*', range_header) or range_header == 'bytes=-':
                    raise HTTPException(416, 'Недопустимый диапазон')
                args['Range'] = range_header
            try:
                obj = app.state.storage.client.get_object(**args)
            except ClientError as e:
                raise HTTPException(416 if e.response['Error']['Code'] == 'InvalidRange' else 404, 'Файл недоступен')
            def stream():
                try:
                    yield from obj['Body'].iter_chunks(64 * 1024)
                finally:
                    obj['Body'].close()
            headers = {'Accept-Ranges': 'bytes', 'Content-Length': str(obj['ContentLength'])}
            if 'ContentRange' in obj:
                headers['Content-Range'] = obj['ContentRange']
            return StreamingResponse(stream(), media_type=media.mime, status_code=206 if range_header else 200, headers=headers)
        path = app.state.storage.root / media.id
        if not path.is_file():
            raise HTTPException(404, 'Файл недоступен')
        return FileResponse(path, media_type=media.mime)

    @app.post('/api/reports', status_code=201)
    def create_report(body: ReportRequest, user=Depends(current_user), db=Depends(get_db)):
        lock_key(db, 'report:' + user.id + str(body.event_id))
        payload = hashlib.sha256(json.dumps(body.model_dump(mode='json'), sort_keys=True).encode()).hexdigest()
        existing = db.scalar(select(Observation).where(Observation.author_id == user.id, Observation.event_id == str(body.event_id)))
        if existing:
            if existing.payload_hash != payload:
                raise HTTPException(409, 'Номер отправки уже использован с другими данными. Обновите список обращений.')
            return report_json(db, existing, True)
        limit(db, settings, 'reports:' + user.id, 20, 3600)
        media = db.scalars(select(Media).where(Media.id.in_([str(i) for i in body.media_ids])).with_for_update()).all()
        if len(media) != len(body.media_ids) or any(m.owner_id != user.id or m.report_id is not None for m in media):
            raise HTTPException(422, 'Вложения недоступны или уже использованы')
        row = Observation(id=uid(), author_id=user.id, event_id=str(body.event_id), payload_hash=payload, **body.model_dump(exclude={'event_id', 'media_ids'}))
        db.add(row)
        db.flush()
        for m in media:
            m.report_id = row.id
        audit(db, user, row, 'submitted', 'Обращение получено. Ожидает проверки инспектором.')
        db.commit()
        return report_json(db, row, True)

    @app.get('/api/reports')
    def reports(status: str | None = None, category: str | None = None, q: str = '', offset: int = 0, user=Depends(current_user), db=Depends(get_db)):
        query = select(Observation).where(Observation.author_id == user.id)
        if status:
            query = query.where(Observation.status == status)
        if category:
            query = query.where(Observation.category == category)
        if q:
            query = query.where(Observation.address.ilike('%' + q[:100] + '%'))
        rows = db.scalars(query.order_by(Observation.received_at.desc(), Observation.id).offset(max(0, offset)).limit(50)).all()
        return [report_json(db, r) for r in rows]

    @app.get('/api/reports/{report_id}')
    def report(report_id: UUID, user=Depends(current_user), db=Depends(get_db)):
        return report_json(db, accessible(db, report_id, user), True)

    @app.post('/api/reports/{report_id}/clarify')
    def clarify(report_id: UUID, body: Clarification, user=Depends(current_user), db=Depends(get_db)):
        row = accessible(db, report_id, user, True)
        if row.author_id != user.id:
            raise HTTPException(403, 'Только автор может дополнить обращение')
        if row.version != body.version or row.status != 'needs_info':
            raise HTTPException(409, 'Обращение изменилось. Обновите страницу.')
        audit(db, user, row, 'clarified', body.note, {'old_address': row.address, 'old_latitude': row.latitude, 'old_longitude': row.longitude})
        row.address, row.latitude, row.longitude = body.address, body.latitude, body.longitude
        row.location_source = 'manual' if body.latitude is not None else 'unknown'
        row.device_accuracy = None
        row.status, row.version, row.updated_at = 'pending', row.version + 1, now()
        db.commit()
        return report_json(db, row, True)

    @app.get('/api/inspector/reports')
    def inspector_reports(status: str | None = None, category: str | None = None, q: str = '', offset: int = 0, user=Depends(inspector), db=Depends(get_db)):
        query = select(Observation)
        if status:
            query = query.where(Observation.status == status)
        if category:
            query = query.where(Observation.category == category)
        if q:
            query = query.where(Observation.address.ilike('%' + q[:100] + '%'))
        rows = db.scalars(query.order_by(Observation.received_at.desc(), Observation.id).offset(max(0, offset)).limit(50)).all()
        return [report_json(db, r) for r in rows]

    @app.post('/api/inspector/reports/{report_id}/decision')
    def decision(report_id: UUID, body: Decision, user=Depends(inspector), db=Depends(get_db)):
        # MVP serializes decisions, not the whole ingest pipeline. Measure before narrowing.
        lock_key(db, 'moderation')
        row = accessible(db, report_id, user, True)
        if row.version != body.version:
            raise HTTPException(409, 'Другой инспектор уже изменил обращение. Обновите страницу.')
        old_incident = row.incident_id
        old = {'status': row.status, 'incident_id': old_incident}
        row.status, row.response = body.status, body.note
        if body.status == 'confirmed':
            target_id = str(body.incident_id) if body.incident_id else None
            incident = db.get(Incident, target_id) if target_id else None
            if target_id and (not incident or not incident.active):
                raise HTTPException(422, 'Выбранный дефект недоступен')
            if incident and incident.category != row.category:
                raise HTTPException(422, 'Выберите дефект той же категории')
            if not incident:
                incident = Incident(id=uid(), category=row.category, latitude=body.latitude, longitude=body.longitude, location_verified=body.location_verified, first_received_at=row.received_at)
                db.add(incident)
                db.flush()
            else:
                # Linking to an existing object does not silently replace its verified location.
                incident.first_received_at = min(incident.first_received_at, row.received_at)
            row.incident_id = incident.id
            if settings.integration_mode == 'simulator' and not db.scalar(select(Outbox).where(Outbox.incident_id == incident.id)):
                db.add(Outbox(incident_id=incident.id))
        else:
            row.incident_id = None
        row.version, row.updated_at = row.version + 1, now()
        db.flush()
        if old_incident and old_incident != row.incident_id:
            remaining = db.scalar(select(func.count()).select_from(Observation).where(Observation.incident_id == old_incident, Observation.status == 'confirmed'))
            if not remaining:
                db.get(Incident, old_incident).active = False
                queued = db.scalar(select(Outbox).where(Outbox.incident_id == old_incident))
                if queued and queued.status == 'queued':
                    queued.status = 'cancelled'
        audit(db, user, row, body.status, body.note, {'before': old, 'after': {'status': row.status, 'incident_id': row.incident_id}})
        db.commit()
        return report_json(db, row, True)

    @app.get('/api/inspector/incidents')
    def incidents(category: str | None = None, latitude: float | None = None, longitude: float | None = None, user=Depends(inspector), db=Depends(get_db)):
        query = select(Incident).where(Incident.active.is_(True))
        if category:
            query = query.where(Incident.category == category)
        if latitude is not None and longitude is not None and engine.dialect.name == 'postgresql':
            query = query.where(text('ST_DWithin(location, ST_SetSRID(ST_MakePoint(:lng,:lat),4326)::geography, 250)')).params(lat=latitude, lng=longitude)
        rows = db.scalars(query.order_by(Incident.created_at.desc()).limit(100)).all()
        return [{'id': r.id, 'category': r.category, 'latitude': r.latitude, 'longitude': r.longitude, 'location_verified': r.location_verified, 'first_received_at': r.first_received_at, 'version': r.version} for r in rows]

    @app.get('/api/inspector/incidents/{incident_id}/observations')
    def incident_observations(incident_id: UUID, user=Depends(inspector), db=Depends(get_db)):
        incident = db.get(Incident, str(incident_id))
        if not incident or not incident.active:
            raise HTTPException(404, 'Дефект не найден')
        rows = db.scalars(select(Observation).where(Observation.incident_id == incident.id).order_by(Observation.received_at, Observation.id).limit(50)).all()
        return [report_json(db, row) for row in rows]

    @app.get('/api/inspector/metrics')
    def metrics(date_from: int | None = Query(default=None, ge=0, le=253402300799), date_to: int | None = Query(default=None, ge=0, le=253402300799), user=Depends(inspector), db=Depends(get_db)):
        if date_from is not None and date_to is not None and date_from >= date_to:
            raise HTTPException(422, 'Неверный период')
        q = select(Incident).where(Incident.active.is_(True))
        if date_from is not None:
            # psycopg casts inferred Integer binds to int32. A valid future
            # filter can exceed that range even when stored dates do not.
            q = q.where(Incident.created_at >= bindparam('date_from', date_from, type_=BigInteger))
        if date_to is not None:
            q = q.where(Incident.created_at < bindparam('date_to', date_to, type_=BigInteger))
        sub = q.subquery()
        total = db.scalar(select(func.count()).select_from(sub))
        verified = db.scalar(select(func.count()).select_from(sub).where(sub.c.location_verified.is_(True)))
        pending = db.scalar(select(func.count()).select_from(Observation).where(Observation.status == 'pending'))
        return {'incidents': total, 'verified': verified, 'unverified': total - verified, 'geolocation_percent': round(100 * verified / total, 1) if total else None, 'target': 90, 'pending_all_time': pending, 'date_from': date_from, 'date_to': date_to}

    @app.post('/api/inspector/incidents/{incident_id}/location')
    def update_location(incident_id: UUID, body: LocationUpdate, user=Depends(inspector), db=Depends(get_db)):
        lock_key(db, 'moderation')
        incident = db.scalar(select(Incident).where(Incident.id == str(incident_id)).with_for_update())
        if not incident or not incident.active:
            raise HTTPException(404, 'Дефект не найден')
        if incident.version != body.version:
            raise HTTPException(409, 'Местоположение уже изменено. Обновите страницу.')
        old = {'latitude': incident.latitude, 'longitude': incident.longitude, 'verified': incident.location_verified}
        incident.latitude, incident.longitude = body.latitude, body.longitude
        incident.location_verified, incident.version = body.location_verified, incident.version + 1
        for row in db.scalars(select(Observation).where(Observation.incident_id == incident.id)):
            audit(db, user, row, 'location_updated', body.note, {'before': old, 'after': body.model_dump()})
        db.commit()
        return {'id': incident.id, 'version': incident.version}

    @app.post('/api/admin/users/{user_id}/role')
    def role(user_id: UUID, body: RoleRequest, user=Depends(current_user), db=Depends(get_db)):
        if user.role != 'admin':
            raise HTTPException(403, 'Доступ только для администратора')
        target = db.get(User, str(user_id))
        if not target or target.id == user.id:
            raise HTTPException(422, 'Нельзя изменить собственную роль или неизвестного пользователя')
        try:
            validate_role_password(target.password_hash, body.role)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from None
        old_role, target.role = target.role, body.role
        audit(db, user, None, 'role_changed', 'Изменена роль пользователя', {'user_id': target.id, 'before': old_role, 'after': body.role})
        db.commit()
        return {'id': target.id, 'role': target.role}

    return app


app = create_app()
