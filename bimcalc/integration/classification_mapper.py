"""Classification code translation service for multi-taxonomy support."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bimcalc.db.models import ClassificationMappingModel


class ClassificationMapper:
    """Translates classification codes between different taxonomies."""

    def __init__(self, session: AsyncSession, org_id: str, project_id: str | None = None):
        self.session = session
        self.org_id = org_id
        self.project_id = project_id
        self._cache: dict[tuple[str, str, str], str | None] = {}

    async def get_project_mapping(self, local_code: str) -> str | None:
        """Look up standard code from project-specific mapping.
        
        Args:
            local_code: Project-specific classification code (e.g., "61")
            
        Returns:
            Standard BIMCalc classification code (e.g., "2601") or None if not found
        """
        if not self.project_id:
            return None
            
        from bimcalc.db.models import ProjectClassificationMappingModel
        
        stmt = select(ProjectClassificationMappingModel.standard_code).where(
            ProjectClassificationMappingModel.org_id == self.org_id,
            ProjectClassificationMappingModel.project_id == self.project_id,
            ProjectClassificationMappingModel.local_code == local_code,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


    async def translate(
        self,
        source_code: str,
        source_scheme: str,
        target_scheme: str
    ) -> str | None:
        """Translate a classification code from source scheme to target scheme."""
        cache_key = (source_scheme, source_code, target_scheme)
        if cache_key in self._cache:
            return self._cache[cache_key]

        stmt = select(ClassificationMappingModel.target_code).where(
            ClassificationMappingModel.org_id == self.org_id,
            ClassificationMappingModel.source_scheme == source_scheme,
            ClassificationMappingModel.source_code == source_code,
            ClassificationMappingModel.target_scheme == target_scheme,
        )

        result = await self.session.execute(stmt)
        target_code = result.scalar_one_or_none()

        self._cache[cache_key] = target_code
        return target_code

    async def translate_batch(
        self,
        codes: list[str],
        source_scheme: str,
        target_scheme: str
    ) -> dict[str, str | None]:
        """Translate multiple codes in one query."""
        if not codes:
            return {}

        stmt = select(
            ClassificationMappingModel.source_code,
            ClassificationMappingModel.target_code,
        ).where(
            ClassificationMappingModel.org_id == self.org_id,
            ClassificationMappingModel.source_scheme == source_scheme,
            ClassificationMappingModel.source_code.in_(codes),
            ClassificationMappingModel.target_scheme == target_scheme,
        )

        result = await self.session.execute(stmt)
        mapping = {row.source_code: row.target_code for row in result}

        return {code: mapping.get(code) for code in codes}

    async def add_mapping(
        self,
        source_code: str,
        source_scheme: str,
        target_code: str,
        target_scheme: str,
        mapping_source: str = "manual",
        confidence: float = 1.0,
        created_by: str = "system",
    ) -> None:
        """Add a new classification mapping to the database."""
        import uuid

        mapping = ClassificationMappingModel(
            id=str(uuid.uuid4()),
            org_id=self.org_id,
            source_scheme=source_scheme,
            source_code=source_code,
            target_scheme=target_scheme,
            target_code=target_code,
            confidence=confidence,
            mapping_source=mapping_source,
            created_by=created_by,
        )

        self.session.add(mapping)
        await self.session.flush()

        cache_key = (source_scheme, source_code, target_scheme)
        self._cache.pop(cache_key, None)
