"""Shared FastAPI dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from kospi_watcher.infrastructure.db import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]
