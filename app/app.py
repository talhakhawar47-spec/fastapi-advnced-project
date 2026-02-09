# app/app.py
from fastapi import FastAPI, HTTPException, File, UploadFile, Form, Depends
from app.schemas import UserRead, UserCreate, UserUpdate, OCRResponse
from app.db import Post, create_db_and_tables, get_async_session, User
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager
from sqlalchemy import select
from app.images import upload_image
from app.ocr import perform_ocr
from app.users import auth_backend, current_active_user, fastapi_users
import os
import uuid
import shutil
import tempfile
import traceback

@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

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
        file: UploadFile = File(...),
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
        "status": "ok",
        "filename": file.filename,
        "model": ocr_result["model"],
        "elapsed_ms": ocr_result["elapsed_ms"],
        "usage": ocr_result["usage"],
        "ocr": ocr_result["content"],
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
