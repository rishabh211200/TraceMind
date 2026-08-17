"""Service repository for managing service metadata and performance baselines."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.service import ServiceModel


class ServiceRepository:
    """Async repository for ServiceModel entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_service(self, name: str) -> ServiceModel | None:
        """Fetch service by unique name."""
        stmt = select(ServiceModel).where(ServiceModel.name == name)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_services(self) -> list[ServiceModel]:
        """List all registered microservices and infrastructure components."""
        stmt = select(ServiceModel).order_by(ServiceModel.name.asc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_service(self, data: dict[str, Any] | ServiceModel) -> ServiceModel:
        """Insert or update service profile."""
        if isinstance(data, ServiceModel):
            service = await self.session.merge(data)
            await self.session.commit()
            return service

        name = data["name"]
        existing = await self.get_service(name)
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            await self.session.commit()
            await self.session.refresh(existing)
            return existing
        else:
            new_service = ServiceModel(**data)
            self.session.add(new_service)
            await self.session.commit()
            await self.session.refresh(new_service)
            return new_service
