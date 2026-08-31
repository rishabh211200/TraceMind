"""Service repository for managing service metadata and performance baselines."""

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from packages.database.models.service import ServiceModel


class ServiceRepository:
    """Async repository for ServiceModel entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_service(self, name: str, tenant_id: str | None = None) -> ServiceModel | None:
        """Fetch service by unique name."""
        stmt = select(ServiceModel).where(ServiceModel.name == name)
        if tenant_id:
            stmt = stmt.where(ServiceModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_services(self, tenant_id: str | None = None) -> list[ServiceModel]:
        """List all registered microservices and infrastructure components."""
        stmt = select(ServiceModel).order_by(ServiceModel.name.asc())
        if tenant_id:
            stmt = stmt.where(ServiceModel.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_service(
        self, data: dict[str, Any] | ServiceModel, tenant_id: str = "tenant_system"
    ) -> ServiceModel:
        """Insert or update service profile."""
        if isinstance(data, ServiceModel):
            if not getattr(data, "tenant_id", None):
                data.tenant_id = tenant_id
            service = await self.session.merge(data)
            await self.session.commit()
            return service

        if "tenant_id" not in data:
            data["tenant_id"] = tenant_id
        name = data["name"]
        existing = await self.get_service(name, tenant_id=data["tenant_id"])
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

    async def update_service(
        self, name: str, updates: dict[str, Any], tenant_id: str | None = None
    ) -> ServiceModel | None:
        """Update fields on an existing service profile."""
        service = await self.get_service(name, tenant_id=tenant_id)
        if not service:
            return None

        for k, v in updates.items():
            if v is not None and hasattr(service, k):
                setattr(service, k, v)

        await self.session.commit()
        await self.session.refresh(service)
        return service


    def _classify_rel_type(self, dep_name: str) -> str:
        if "cache" in dep_name:
            return "CACHE_LOOKUP"
        if "db" in dep_name or "database" in dep_name:
            return "DB_QUERY"
        if "gateway" in dep_name:
            return "GATEWAY_CALL"
        return "HTTP_RPC"

    def _extract_declared_edges(
        self,
        service_name: str,
        dependencies: list[Any],
        edge_keys: set[tuple[str, str]],
    ) -> list[dict[str, Any]]:
        edges = []
        for dep in dependencies:
            if isinstance(dep, str):
                rel_type = self._classify_rel_type(dep)
                key = (service_name, dep)
                if key not in edge_keys:
                    edge_keys.add(key)
                    edges.append(
                        {
                            "from_service": service_name,
                            "to_service": dep,
                            "relationship_type": rel_type,
                            "call_weight": 1.0,
                            "metadata": {},
                        }
                    )
            elif isinstance(dep, dict) and "to" in dep:
                target = dep["to"]
                key = (service_name, target)
                if key not in edge_keys:
                    edge_keys.add(key)
                    edges.append(
                        {
                            "from_service": service_name,
                            "to_service": target,
                            "relationship_type": dep.get("type", "HTTP_RPC"),
                            "call_weight": float(dep.get("weight", 1.0)),
                            "metadata": dep.get("metadata", {}),
                        }
                    )
        return edges

    async def get_service_topology(self) -> dict[str, Any]:
        """Derive the complete system dependency graph topology."""
        services = await self.list_services()
        nodes = []
        edges = []
        edge_keys: set[tuple[str, str]] = set()

        # Known architectural infrastructure dependencies
        infra_deps = {
            "api-gateway": [("auth-service", "HTTP_RPC")],
            "customer-service": [
                ("customer-cache", "CACHE_LOOKUP"),
                ("customer-db", "DB_QUERY"),
            ],
            "inventory-service": [("inventory-db", "DB_QUERY")],
            "payment-service": [("payment-gateway", "GATEWAY_CALL")],
        }

        for svc in services:
            nodes.append(
                {
                    "id": svc.name,
                    "name": svc.name,
                    "type": svc.service_type,
                    "capacity": svc.capacity,
                    "baseline_latency_ms": svc.baseline_latency_ms,
                }
            )

            deps = svc.dependencies if isinstance(svc.dependencies, list) else []
            edges.extend(self._extract_declared_edges(svc.name, deps, edge_keys))

            if svc.name in infra_deps:
                for target, rel_type in infra_deps[svc.name]:
                    key = (svc.name, target)
                    if key not in edge_keys:
                        edge_keys.add(key)
                        edges.append(
                            {
                                "from_service": svc.name,
                                "to_service": target,
                                "relationship_type": rel_type,
                                "call_weight": 1.0,
                                "metadata": {},
                            }
                        )

        return {
            "nodes": nodes,
            "edges": edges,
            "total_services": len(nodes),
            "total_dependencies": len(edges),
        }
