# app/app.py
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.schemas import UserRead, UserCreate, UserUpdate, ScanOCRRequest, OCRResponse
from app.db import Post, create_db_and_tables, get_async_session, User
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.images import upload_image
from app.ocr import perform_ocr, decode_image_payload, DEFAULT_OCR_MIME_TYPE
from app.users import auth_backend, current_active_user, fastapi_users
import base64
import os
import uuid
import shutil
import tempfile
import traceback

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui() -> HTMLResponse:
    swagger_html = get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_ui_parameters={
            "tryItOutEnabled": True,
            "persistAuthorization": True,
        },
    )
    page = swagger_html.body.decode("utf-8").replace(
        "</body>",
        '<script src="/static/swagger-camera.js"></script></body>',
    )
    return HTMLResponse(content=page, status_code=200)

# AUTH ROUTES
app.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix='/auth/jwt',
    tags=["auth"]
)

app.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    tags=["auth"]
)

app.include_router(
    fastapi_users.get_reset_password_router(),
    prefix="/auth",
    tags=["auth"]
)

app.include_router(
    fastapi_users.get_verify_router(UserRead),
    prefix="/auth",
    tags=["auth"]
)

app.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"]
)

# UPLOAD POST
@app.post("/upload")
async def upload_file(
        file: UploadFile = File(...),
        caption: str = Form(""),
        user: User = Depends(current_active_user),
        session: AsyncSession = Depends(get_async_session)
):
    temp_file_path = None

    try:
        # save temporary file
        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=os.path.splitext(file.filename)[1]
        ) as temp_file:
            temp_file_path = temp_file.name
            shutil.copyfileobj(file.file, temp_file)

        # upload to ImageKit
        upload_result = upload_image(temp_file_path, file_name=file.filename)

        # In imagekitio 5.1.0, upload directly returns the FileUploadResponse object
        # and success is implied if no exception was raised.
        if upload_result and upload_result.url:
            post = Post(
                user_id=user.id,
                caption=caption,
                url=upload_result.url,
                file_type="video" if file.content_type and file.content_type.startswith("video/") else "image",
                file_name=upload_result.name
            )

            session.add(post)
            await session.commit()
            await session.refresh(post)
            return post

        raise HTTPException(status_code=500, detail="Upload failed")

    except Exception as e:
        print(f"--- UPLOAD ERROR ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        if temp_file_path and os.path.exists(temp_file_path):
            os.unlink(temp_file_path)
        file.file.close()



@app.post("/ocr", response_model=OCRResponse)
async def ocr_document(
           file: UploadFile = File(
            ...,
            description=(
                "Upload or capture a document image. On mobile devices, this file "
                "picker can open the camera directly."
            ),
        ),
        user: User = Depends(current_active_user)
):
    if not file.content_type:
        raise HTTPException(status_code=400, detail="File content type is required")

    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image uploads are supported")

    image_bytes = await file.read()
    try:
        ocr_result = await perform_ocr(image_bytes, file.content_type, file.filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": ocr_result["status"],
        "filename": file.filename,
        "model": ocr_result["model"],
        "elapsed_ms": ocr_result["elapsed_ms"],
        "usage": ocr_result["usage"],
        "ocr": ocr_result["content"],
        "ocr_raw": ocr_result["raw_content"],
        "ocr_parse_error": ocr_result["parse_error"],
    }



@app.post("/scan-ocr", response_model=OCRResponse)
async def scan_ocr_document(
        file: UploadFile | None = File(None),
        image_data: str | None = Form(None),
        filename: str | None = Form(None),
        mime_type: str | None = Form(None),
        user: User = Depends(current_active_user)
):
    is_file_provided = file is not None and file.filename != ""
    is_data_provided = image_data is not None and image_data.strip() != ""

    if not is_file_provided and not is_data_provided:
        raise HTTPException(status_code=400, detail="Upload a file or provide image_data")

    if is_file_provided and is_data_provided:
        raise HTTPException(status_code=400, detail="Provide either file or image_data, not both")

    if is_file_provided:
        # We checked file is not None above, but for type hinting we can use an assertion
        assert file is not None 
        if not file.content_type:
            raise HTTPException(status_code=400, detail="File content type is required")

        if not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image uploads are supported")

        image_bytes = await file.read()
        resolved_mime_type = file.content_type
        resolved_filename = file.filename
    else:
        resolved_filename = filename or "scan-ocr"
        try:
            image_bytes, resolved_mime_type = decode_image_payload(image_data)
        except (TypeError, ValueError, IndexError) as exc:
            raise HTTPException(status_code=400, detail="image_data must be valid base64 or data URL") from exc
        
        if mime_type: # override if explicitly provided
             resolved_mime_type = mime_type

    try:
        ocr_result = await perform_ocr(image_bytes, resolved_mime_type, resolved_filename)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "status": ocr_result["status"],
        "filename": resolved_filename,
        "model": ocr_result["model"],
        "elapsed_ms": ocr_result["elapsed_ms"],
        "usage": ocr_result["usage"],
        "ocr": ocr_result["content"],
        "ocr_raw": ocr_result["raw_content"],
        "ocr_parse_error": ocr_result["parse_error"],
    }



#FEED
@app.get("/feed")
async def get_feed(
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    try:
        # get posts ordered by newest
        result = await session.execute(select(Post).order_by(Post.created_at.desc()))
        posts = result.scalars().all()

        # get users put email
        result = await session.execute(select(User))
        users = result.scalars().all()
        user_dict = {u.id: u.email for u in users}

        posts_data = []
        for post in posts:
            posts_data.append({
                "id": str(post.id),
                "user_id": str(post.user_id),
                "caption": post.caption,
                "url": post.url,
                "file_type": post.file_type,
                "file_name": post.file_name,
                "created_at": post.created_at.isoformat() if post.created_at else None,
                "is_owner": post.user_id == user.id,
                "email": user_dict.get(post.user_id, "Unknown")
            })

        return {"posts": posts_data}
    except Exception as e:
        print(f"--- FEED ERROR ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


# DELETE POST 
@app.delete("/posts/{post_id}")
async def delete_post(
        post_id: str,
        session: AsyncSession = Depends(get_async_session),
        user: User = Depends(current_active_user)
):
    try:
        post_uuid = uuid.UUID(post_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid post ID format")

    try:
        result = await session.execute(select(Post).where(Post.id == post_uuid))
        post = result.scalars().first()

        if not post:
            raise HTTPException(status_code=404, detail="Post not found")

        if post.user_id != user.id:
            raise HTTPException(status_code=403, detail="You don't have permission to delete this post")

        await session.delete(post)
        await session.commit()

        return {"success": True, "message": "Post deleted successfully"}

    except Exception as e:
        print(f"--- DELETE ERROR ---")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
