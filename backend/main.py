from __future__ import annotations

import json
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.agent_engine import autogen_available
from backend.analytics import dashboard_snapshot, filter_options, marketing_data, sales_data
from backend.config import settings
from backend.database import Base, engine, get_db
from backend.datasets import (
    MAX_UPLOAD_BYTES,
    DatasetError,
    column_types,
    parse_upload,
    standardize_dataset,
    suggest_mapping,
    validate_mapping,
)
from backend.delivery import send_email, send_telegram
from backend.models import Dataset, Report, User
from backend.report_engine import build_title, generate_report, report_summary
from backend.schemas import (
    AuthResponse,
    DeliveryRequest,
    DatasetDetail,
    DatasetListItem,
    DatasetMappingRequest,
    FavoriteRequest,
    GenerateReportRequest,
    LoginRequest,
    RegisterRequest,
    ReportDetail,
    ReportListItem,
    UserOut,
)
from backend.security import (
    clear_session_cookie,
    create_session_token,
    get_current_user,
    hash_password,
    set_session_cookie,
    verify_password,
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.environment == "production" and settings.jwt_secret == "local-development-secret-change-me":
        raise RuntimeError("JWT_SECRET must be configured in production")
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="AI Analytic Platform API",
    version="2.0.0",
    description="Authenticated sales and marketing intelligence platform",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(), payment=()")
    if settings.environment == "production":
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


def _user_out(user: User) -> UserOut:
    return UserOut.model_validate(user)


def _owned_report(db: Session, user: User, report_id: str) -> Report:
    report = db.scalar(
        select(Report).where(Report.id == report_id, Report.user_id == user.id)
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


def _owned_dataset(db: Session, user: User, dataset_id: str) -> Dataset:
    dataset = db.scalar(select(Dataset).where(Dataset.id == dataset_id, Dataset.user_id == user.id))
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


def _dataset_detail(dataset: Dataset) -> DatasetDetail:
    value = DatasetListItem.model_validate(dataset).model_dump()
    return DatasetDetail(**value, preview=(dataset.raw_rows or [])[:8])


def _dataset_sources(
    db: Session,
    user: User,
    dataset_id: str | None,
) -> tuple[list[dict] | None, list[dict] | None, Dataset | None]:
    if not dataset_id:
        return None, None, None
    dataset = _owned_dataset(db, user, dataset_id)
    try:
        sales, marketing = standardize_dataset(dataset)
    except DatasetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return sales, marketing, dataset


def _clean_filters(**values: str | None) -> dict[str, str]:
    return {
        key: value.strip()
        for key, value in values.items()
        if isinstance(value, str) and value.strip()
    }


@app.get("/api/health", tags=["system"])
def health(db: Session = Depends(get_db)) -> dict:
    db.execute(text("SELECT 1"))
    return {"status": "healthy", "service": "ai-analytic-platform-api", "version": "2.0.0"}


@app.post(
    "/api/auth/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["authentication"],
)
def register(payload: RegisterRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status_code=409, detail="An account with this email already exists")

    user = User(name=payload.name, email=email, password_hash=hash_password(payload.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this email already exists") from exc
    db.refresh(user)
    set_session_cookie(response, create_session_token(user.id))
    return AuthResponse(user=_user_out(user), message="Account created")


@app.post("/api/auth/login", response_model=AuthResponse, tags=["authentication"])
def login(payload: LoginRequest, response: Response, db: Session = Depends(get_db)) -> AuthResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    set_session_cookie(response, create_session_token(user.id))
    return AuthResponse(user=_user_out(user), message="Welcome back")


@app.post("/api/auth/logout", status_code=status.HTTP_204_NO_CONTENT, tags=["authentication"])
def logout(response: Response) -> Response:
    clear_session_cookie(response)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@app.get("/api/auth/me", response_model=UserOut, tags=["authentication"])
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _user_out(user)


@app.get("/api/meta/options", tags=["intelligence"])
def options(
    dataset_id: str | None = Query(default=None, max_length=36),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    sales, marketing, _ = _dataset_sources(db, user, dataset_id)
    return filter_options(sales, marketing)


@app.get("/api/system/status", tags=["system"])
def system_status(_: User = Depends(get_current_user)) -> dict:
    runtime_ready = autogen_available()
    agent_enabled = runtime_ready and bool(settings.groq_api_key)
    if agent_enabled:
        ai_mode = "Microsoft AutoGen · GROQ"
    elif runtime_ready:
        ai_mode = "Verified analytics · AutoGen ready"
    else:
        ai_mode = "Verified local analytics"
    return {
        "ai_mode": ai_mode,
        "model": settings.groq_model if agent_enabled else None,
        "autogen_available": runtime_ready,
        "autogen_enabled": agent_enabled,
        "agent_pipeline": ["Data Analyst", "Report Writer", "Independent Critic"],
        "email_delivery": bool(os.getenv("GMAIL_USER")),
        "telegram_delivery": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "dataset_records": len(sales_data()) + len(marketing_data()),
    }


@app.post(
    "/api/datasets/upload",
    response_model=DatasetDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["datasets"],
)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(default=""),
    kind: str = Form(default="auto"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetDetail:
    if kind not in {"auto", "sales", "marketing"}:
        raise HTTPException(status_code=422, detail="Dataset type must be auto, sales, or marketing")
    payload = await file.read(MAX_UPLOAD_BYTES + 1)
    try:
        rows, columns = parse_upload(file.filename or "dataset", payload)
        types = column_types(rows, columns)
        detected_kind, mapping, dataset_status = suggest_mapping(columns, types, kind)
    except DatasetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    default_name = Path(file.filename or "New dataset").stem.replace("_", " ").replace("-", " ")
    dataset_name = " ".join((name.strip() or default_name).split())[:120]
    dataset = Dataset(
        user_id=user.id,
        name=dataset_name or "New dataset",
        original_filename=(file.filename or "dataset")[:255],
        kind=detected_kind,
        status=dataset_status,
        row_count=len(rows),
        columns=columns,
        column_types=types,
        mapping=mapping,
        raw_rows=rows,
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return _dataset_detail(dataset)


@app.get("/api/datasets", response_model=list[DatasetListItem], tags=["datasets"])
def list_datasets(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[DatasetListItem]:
    datasets = db.scalars(
        select(Dataset).where(Dataset.user_id == user.id).order_by(Dataset.created_at.desc())
    ).all()
    return [DatasetListItem.model_validate(dataset) for dataset in datasets]


@app.get("/api/datasets/{dataset_id}", response_model=DatasetDetail, tags=["datasets"])
def get_dataset(
    dataset_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetDetail:
    return _dataset_detail(_owned_dataset(db, user, dataset_id))


@app.patch("/api/datasets/{dataset_id}/mapping", response_model=DatasetDetail, tags=["datasets"])
def update_dataset_mapping(
    dataset_id: str,
    payload: DatasetMappingRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> DatasetDetail:
    dataset = _owned_dataset(db, user, dataset_id)
    try:
        mapping = validate_mapping(payload.kind, payload.mapping, dataset.columns)
    except DatasetError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    dataset.kind = payload.kind
    dataset.mapping = mapping
    dataset.status = "ready"
    db.commit()
    db.refresh(dataset)
    return _dataset_detail(dataset)


@app.delete("/api/datasets/{dataset_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["datasets"])
def delete_dataset(
    dataset_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    db.delete(_owned_dataset(db, user, dataset_id))
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/dataset-templates/{kind}", tags=["datasets"])
def dataset_template(kind: str, _: User = Depends(get_current_user)) -> PlainTextResponse:
    if kind == "sales":
        body = "product,region,quarter,revenue,units_sold,category\nAnalytics Pro,India,Q1 2026,125000,84,SaaS\n"
    elif kind == "marketing":
        body = "campaign_name,channel,quarter,budget,impressions,clicks,conversions\nLaunch Campaign,Email,Q1 2026,5000,120000,6200,410\n"
    else:
        raise HTTPException(status_code=404, detail="Template not found")
    return PlainTextResponse(
        body,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="ai-analytic-platform-{kind}-template.csv"'},
    )


@app.get("/api/dashboard", tags=["intelligence"])
def dashboard(
    dataset_id: str | None = Query(default=None, max_length=36),
    region: str | None = Query(default=None, max_length=80),
    quarter: str | None = Query(default=None, max_length=30),
    product: str | None = Query(default=None, max_length=120),
    channel: str | None = Query(default=None, max_length=120),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    sales, marketing, dataset = _dataset_sources(db, user, dataset_id)
    snapshot = dashboard_snapshot(_clean_filters(
        region=region,
        quarter=quarter,
        product=product,
        channel=channel,
    ), sales, marketing)
    snapshot["dataset"] = {
        "id": dataset.id,
        "name": dataset.name,
        "kind": dataset.kind,
    } if dataset else {"id": None, "name": "Bundled demo data", "kind": "combined"}
    recent = db.scalars(
        select(Report)
        .where(Report.user_id == user.id)
        .order_by(Report.created_at.desc())
        .limit(4)
    ).all()
    snapshot["recent_reports"] = [
        ReportListItem.model_validate(item).model_dump(mode="json") for item in recent
    ]
    snapshot["report_count"] = db.scalar(
        select(func.count(Report.id)).where(Report.user_id == user.id)
    ) or 0
    return snapshot


@app.post(
    "/api/reports/generate",
    response_model=ReportDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["reports"],
)
async def create_report(
    payload: GenerateReportRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDetail:
    if payload.report_type == "custom" and not payload.question:
        raise HTTPException(status_code=422, detail="A question is required for a custom report")

    filters = payload.filters.cleaned()
    sales, marketing, dataset = _dataset_sources(db, user, payload.dataset_id)
    snapshot = dashboard_snapshot(filters, sales, marketing)
    if not snapshot["coverage"]["sales_records"] and not snapshot["coverage"]["marketing_records"]:
        raise HTTPException(status_code=422, detail="No dataset rows match these filters")

    content, provider = await run_in_threadpool(
        generate_report,
        payload.report_type,
        filters,
        payload.focus,
        payload.question,
        snapshot,
    )
    stored_filters = dict(filters)
    if dataset:
        stored_filters["dataset"] = dataset.name
    report = Report(
        user_id=user.id,
        title=build_title(payload.report_type, filters),
        report_type=payload.report_type,
        dataset_id=dataset.id if dataset else None,
        content=content,
        summary=report_summary(snapshot),
        provider=provider,
        report_filters=stored_filters,
        metrics=snapshot["kpis"],
        chart_data=snapshot["charts"],
        insights=snapshot["insights"],
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return ReportDetail.model_validate(report)


@app.get("/api/reports", response_model=list[ReportListItem], tags=["reports"])
def list_reports(
    search: str = Query(default="", max_length=120),
    report_type: str | None = Query(default=None, max_length=40),
    favorite: bool | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[ReportListItem]:
    statement = select(Report).where(Report.user_id == user.id)
    if search.strip():
        term = f"%{search.strip()}%"
        statement = statement.where(or_(Report.title.ilike(term), Report.summary.ilike(term)))
    if report_type:
        statement = statement.where(Report.report_type == report_type)
    if favorite is not None:
        statement = statement.where(Report.favorite == favorite)
    reports = db.scalars(
        statement.order_by(Report.created_at.desc()).offset(offset).limit(limit)
    ).all()
    return [ReportListItem.model_validate(item) for item in reports]


@app.get("/api/reports/{report_id}", response_model=ReportDetail, tags=["reports"])
def get_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDetail:
    return ReportDetail.model_validate(_owned_report(db, user, report_id))


@app.patch("/api/reports/{report_id}/favorite", response_model=ReportDetail, tags=["reports"])
def favorite_report(
    report_id: str,
    payload: FavoriteRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ReportDetail:
    report = _owned_report(db, user, report_id)
    report.favorite = payload.favorite
    db.commit()
    db.refresh(report)
    return ReportDetail.model_validate(report)


@app.delete("/api/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["reports"])
def delete_report(
    report_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    report = _owned_report(db, user, report_id)
    db.delete(report)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/api/reports/{report_id}/download", tags=["reports"])
def download_report(
    report_id: str,
    format: str = Query(default="markdown", pattern="^(markdown|json)$"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> PlainTextResponse:
    report = _owned_report(db, user, report_id)
    safe_name = re.sub(r"[^a-z0-9]+", "-", report.title.lower()).strip("-")[:80]
    if format == "json":
        body = json.dumps(
            {
                "title": report.title,
                "type": report.report_type,
                "created_at": report.created_at.isoformat(),
                "filters": report.report_filters,
                "metrics": report.metrics,
                "chart_data": report.chart_data,
                "insights": report.insights,
                "content": report.content,
            },
            indent=2,
            ensure_ascii=False,
        )
        media_type = "application/json"
        extension = "json"
    else:
        body = report.content
        media_type = "text/markdown"
        extension = "md"
    return PlainTextResponse(
        body,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{safe_name}.{extension}"'},
    )


@app.post("/api/reports/{report_id}/deliver", tags=["reports"])
async def deliver_report(
    report_id: str,
    payload: DeliveryRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    report = _owned_report(db, user, report_id)
    try:
        if payload.channel == "email":
            await run_in_threadpool(send_email, payload.destination, report.title, report.content)
        else:
            await run_in_threadpool(send_telegram, payload.destination, report.title, report.content)
    except Exception as exc:
        message = str(exc) if "not configured" in str(exc) else "Delivery failed. Check the integration settings."
        raise HTTPException(status_code=503, detail=message) from exc
    return {"message": f"Report sent by {payload.channel}"}


frontend = Path(settings.frontend_dir)
assets = frontend / "assets"
if assets.is_dir():
    app.mount("/assets", StaticFiles(directory=assets), name="frontend-assets")


@app.get("/{full_path:path}", include_in_schema=False)
def frontend_app(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API route not found")
    if frontend.is_dir():
        requested = (frontend / full_path).resolve()
        if requested.is_file() and frontend.resolve() in requested.parents:
            return FileResponse(requested)
        index = frontend / "index.html"
        if index.is_file():
            return FileResponse(index)
    return {
        "name": settings.app_name,
        "message": "Frontend build not found. Run the frontend build or open /api/docs.",
    }
