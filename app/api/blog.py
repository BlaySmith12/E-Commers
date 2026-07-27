"""Blog Post REST API."""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.catalog import BlogPost, User
from app.schemas import MessageOut
from app.security import AdminUser, CurrentUser
from app.audit import log_audit

router = APIRouter(prefix='/blog', tags=['Blog'])


class BlogPostCreate(BaseModel):
    title: str
    slug: str
    content: Optional[str] = None
    excerpt: Optional[str] = None
    image_url: Optional[str] = None
    is_published: bool = False


class BlogPostUpdate(BaseModel):
    title: Optional[str] = None
    slug: Optional[str] = None
    content: Optional[str] = None
    excerpt: Optional[str] = None
    image_url: Optional[str] = None
    is_published: Optional[bool] = None


class BlogPostOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    title: str
    slug: str
    content: Optional[str] = None
    excerpt: Optional[str] = None
    image_url: Optional[str] = None
    author_id: Optional[int] = None
    is_published: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class BlogAuthorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class BlogPostDetailOut(BlogPostOut):
    author: Optional[BlogAuthorOut] = None


# ----------------------------- Public -----------------------------
@router.get('', response_model=List[BlogPostOut])
async def list_posts(
    db: AsyncSession = Depends(get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    stmt = (
        select(BlogPost)
        .where(BlogPost.is_published == True)  # noqa: E712
        .order_by(BlogPost.created_at.desc())
        .offset(skip).limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get('/{slug}', response_model=BlogPostDetailOut)
async def get_post_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BlogPost).where(BlogPost.slug == slug, BlogPost.is_published == True)
    )
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail='Blog post not found')
    return post


# ----------------------------- Admin CRUD -----------------------------
@router.post('', response_model=BlogPostOut, status_code=status.HTTP_201_CREATED)
async def create_post(
    payload: BlogPostCreate, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    dup = await db.execute(select(BlogPost).where(BlogPost.slug == payload.slug))
    if dup.scalar_one_or_none():
        raise HTTPException(status_code=400, detail='Slug already exists')
    post = BlogPost(**payload.model_dump(), author_id=admin.id)
    db.add(post)
    await db.commit()
    await db.refresh(post)
    await log_audit(
        db=db, action="CREATE", entity_type="BlogPost", entity_id=post.id,
        user_id=admin.id, details=f"Created blog post: {post.title}"
    )
    return post


@router.put('/{post_id}', response_model=BlogPostOut)
async def update_post(
    post_id: int, payload: BlogPostUpdate,
    db: AsyncSession = Depends(get_db), admin: AdminUser = None,
):
    result = await db.execute(select(BlogPost).where(BlogPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail='Blog post not found')
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(post, field, value)
    await db.commit()
    await db.refresh(post)
    await log_audit(
        db=db, action="UPDATE", entity_type="BlogPost", entity_id=post.id,
        user_id=admin.id, details=f"Updated blog post: {post.title}"
    )
    return post


@router.delete('/{post_id}', response_model=MessageOut)
async def delete_post(
    post_id: int, db: AsyncSession = Depends(get_db), admin: AdminUser = None
):
    result = await db.execute(select(BlogPost).where(BlogPost.id == post_id))
    post = result.scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail='Blog post not found')
    title = post.title
    await db.delete(post)
    await db.commit()
    await log_audit(
        db=db, action="DELETE", entity_type="BlogPost", entity_id=post_id,
        user_id=admin.id, details=f"Deleted blog post: {title}"
    )
    return MessageOut(detail='Blog post deleted')
