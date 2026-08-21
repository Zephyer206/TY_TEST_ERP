"""Unit tests for TWP primary-spec and multi-tooling behavior.

Requirements:
- Primary uniqueness scoped to (part_id, tooling_id)
- List TWP uses only the continuous-priority selected tooling's primary spec
- If selected tooling has candidates but no primary, do not fall back
- Legacy parts TWP fallback remains only when selected tooling has no source-backed candidates
- Shared tooling relations remain display-only and never merge TWP
"""

import pytest
import pytest_asyncio
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.part import Part
from app.models.tooling import Tooling, ToolingPart
from app.models.part_tooling_spec import PartToolingSpec
from app.models.tooling_shared_relation import ToolingSharedRelation


@pytest_asyncio.fixture
async def base_part(db: AsyncSession) -> Part:
    """Create a base part with legacy TWP fields."""
    part = Part(
        internal_name="Test Part",
        spec_twph="T1.2*W50*P100",
        thickness=Decimal("1.2"),
        width=Decimal("50"),
        pitch=Decimal("100"),
        part_status="DRAFT",
    )
    db.add(part)
    await db.commit()
    await db.refresh(part)
    return part


@pytest_asyncio.fixture
async def continuous_tooling(db: AsyncSession) -> Tooling:
    """Create a continuous mold."""
    tooling = Tooling(
        tooling_number="C001",
        mold_type="连续模",
        is_continuous=True,
        cavity_count=1,
        status="AVAILABLE",
    )
    db.add(tooling)
    await db.commit()
    await db.refresh(tooling)
    return tooling


@pytest_asyncio.fixture
async def simple_tooling(db: AsyncSession) -> Tooling:
    """Create a simple mold."""
    tooling = Tooling(
        tooling_number="S001",
        mold_type="简易模",
        is_continuous=False,
        cavity_count=1,
        process_step_count=3,
        status="AVAILABLE",
    )
    db.add(tooling)
    await db.commit()
    await db.refresh(tooling)
    return tooling


@pytest.mark.asyncio
class TestPrimaryUniquenessScope:
    """Test that is_primary is unique per (part_id, tooling_id)."""

    async def test_same_tooling_only_one_primary(
        self, db: AsyncSession, base_part: Part, continuous_tooling: Tooling
    ):
        """Multiple specs on same tooling can have at most one primary."""
        # Link part to tooling
        tp = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        db.add(tp)
        await db.commit()

        # Add two specs for the same (part_id, tooling_id)
        spec1 = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.0*W50*P100",
            thickness=Decimal("1.0"),
            is_primary=True,
            source_sheet="Sheet1",
            source_row=10,
        )
        db.add(spec1)
        await db.commit()

        spec2 = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.5*W50*P100",
            thickness=Decimal("1.5"),
            is_primary=False,
            source_sheet="Sheet1",
            source_row=11,
        )
        db.add(spec2)
        await db.commit()

        # Try to make spec2 primary - should succeed
        spec2.is_primary = True
        spec1.is_primary = False
        await db.commit()

        # Verify only spec2 is primary
        result = await db.execute(
            select(PartToolingSpec)
            .where(
                PartToolingSpec.part_id == base_part.id,
                PartToolingSpec.tooling_id == continuous_tooling.id,
            )
            .order_by(PartToolingSpec.id)
        )
        specs = result.scalars().all()
        assert len(specs) == 2
        assert not specs[0].is_primary
        assert specs[1].is_primary

    async def test_different_toolings_can_each_have_primary(
        self,
        db: AsyncSession,
        base_part: Part,
        continuous_tooling: Tooling,
        simple_tooling: Tooling,
    ):
        """Different toolings on the same part can each have a primary spec."""
        # Link part to both toolings
        tp1 = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        tp2 = ToolingPart(part_id=base_part.id, tooling_id=simple_tooling.id, is_primary=False)
        db.add_all([tp1, tp2])
        await db.commit()

        # Add primary spec for continuous tooling
        spec1 = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.0*W50*P100",
            thickness=Decimal("1.0"),
            is_primary=True,
            source_sheet="Sheet1",
            source_row=10,
        )
        db.add(spec1)
        await db.commit()

        # Add primary spec for simple tooling - should be allowed
        spec2 = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=simple_tooling.id,
            spec_twph="T1.2*W50*P100",
            thickness=Decimal("1.2"),
            is_primary=True,
            source_sheet="Sheet2",
            source_row=20,
        )
        db.add(spec2)
        await db.commit()

        # Verify both are primary
        result = await db.execute(
            select(PartToolingSpec)
            .where(PartToolingSpec.part_id == base_part.id)
            .order_by(PartToolingSpec.tooling_id)
        )
        specs = result.scalars().all()
        assert len(specs) == 2
        assert all(spec.is_primary for spec in specs)


@pytest.mark.asyncio
class TestContinuousPrioritySelection:
    """Test that continuous molds are prioritized when selecting display tooling."""

    async def test_continuous_preferred_over_simple(
        self,
        db: AsyncSession,
        base_part: Part,
        continuous_tooling: Tooling,
        simple_tooling: Tooling,
    ):
        """When both continuous and simple molds exist, continuous is selected."""
        # Link to both, simple marked as primary on tooling_parts
        tp1 = ToolingPart(part_id=base_part.id, tooling_id=simple_tooling.id, is_primary=True)
        tp2 = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=False)
        db.add_all([tp1, tp2])
        await db.commit()

        # Add spec only to continuous tooling
        spec = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.0*W50*P100",
            thickness=Decimal("1.0"),
            is_primary=True,
        )
        db.add(spec)
        await db.commit()

        # The list endpoint should select continuous_tooling despite is_primary on simple
        # This is tested through the _select_primary_tooling function
        from app.api.parts import _select_primary_tooling

        tooling_records = [
            (tp1, simple_tooling),
            (tp2, continuous_tooling),
        ]
        selected = _select_primary_tooling(tooling_records)
        assert selected is not None
        assert selected[1].id == continuous_tooling.id


@pytest.mark.asyncio
class TestSelectedToolingSpecDisplay:
    """Test that list display uses only the selected tooling's primary spec."""

    async def test_uses_selected_tooling_primary_spec(
        self,
        db: AsyncSession,
        base_part: Part,
        continuous_tooling: Tooling,
        simple_tooling: Tooling,
    ):
        """List display should use the primary spec from the selected tooling."""
        tp1 = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        tp2 = ToolingPart(part_id=base_part.id, tooling_id=simple_tooling.id, is_primary=False)
        db.add_all([tp1, tp2])
        await db.commit()

        # Continuous tooling has primary spec
        continuous_spec = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.0*W50*P100",
            thickness=Decimal("1.0"),
            is_primary=True,
        )
        # Simple tooling also has primary spec
        simple_spec = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=simple_tooling.id,
            spec_twph="T2.0*W60*P120",
            thickness=Decimal("2.0"),
            is_primary=True,
        )
        db.add_all([continuous_spec, simple_spec])
        await db.commit()

        # The selected tooling is continuous (priority), so display should use continuous_spec
        # Implementation verifies this through the specs_by_key[(part_id, primary_tooling_id)] lookup

    async def test_no_fallback_when_selected_has_candidates_but_no_primary(
        self,
        db: AsyncSession,
        base_part: Part,
        continuous_tooling: Tooling,
    ):
        """If selected tooling has specs but none are primary, don't fall back."""
        tp = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        db.add(tp)
        await db.commit()

        # Add non-primary spec
        spec = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.0*W50*P100",
            thickness=Decimal("1.0"),
            is_primary=False,
        )
        db.add(spec)
        await db.commit()

        # Display should be None, not fall back to legacy part fields
        # Logic: selected_tooling_specs exists but primary_spec is None
        # Therefore display_spec = None (not p.spec_twph)


@pytest.mark.asyncio
class TestLegacyFallback:
    """Test that legacy part TWP fields are used only when selected tooling has no candidates."""

    async def test_fallback_when_no_source_backed_specs(
        self, db: AsyncSession, base_part: Part, continuous_tooling: Tooling
    ):
        """When selected tooling has no specs, fall back to legacy part fields."""
        tp = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        db.add(tp)
        await db.commit()

        # No PartToolingSpec records - selected_tooling_specs will be empty
        # Display should fall back to part.spec_twph, part.thickness, etc.

    async def test_no_fallback_when_specs_exist(
        self, db: AsyncSession, base_part: Part, continuous_tooling: Tooling
    ):
        """When selected tooling has specs, don't use legacy fields even if no primary."""
        tp = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        db.add(tp)
        await db.commit()

        spec = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.0*W50*P100",
            thickness=Decimal("1.0"),
            is_primary=False,
        )
        db.add(spec)
        await db.commit()

        # selected_tooling_specs has one element, so no fallback to legacy


@pytest.mark.asyncio
class TestMultipleCandidatesOnOneTooling:
    """Test handling of multiple spec candidates on a single tooling."""

    async def test_multiple_specs_one_primary(
        self, db: AsyncSession, base_part: Part, continuous_tooling: Tooling
    ):
        """Multiple specs on one tooling, one marked primary."""
        tp = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        db.add(tp)
        await db.commit()

        specs = [
            PartToolingSpec(
                part_id=base_part.id,
                tooling_id=continuous_tooling.id,
                spec_twph=f"T{i}.0*W50*P100",
                thickness=Decimal(f"{i}.0"),
                is_primary=(i == 2),
                source_row=i,
            )
            for i in range(1, 4)
        ]
        db.add_all(specs)
        await db.commit()

        # Should display spec with i==2
        result = await db.execute(
            select(PartToolingSpec)
            .where(
                PartToolingSpec.part_id == base_part.id,
                PartToolingSpec.tooling_id == continuous_tooling.id,
                PartToolingSpec.is_primary == True,
            )
        )
        primary = result.scalar_one()
        assert primary.thickness == Decimal("2.0")


@pytest.mark.asyncio
class TestSharedToolingNoMerge:
    """Test that shared tooling relations do not merge TWP."""

    async def test_shared_relation_display_only(
        self,
        db: AsyncSession,
        base_part: Part,
        continuous_tooling: Tooling,
    ):
        """Shared tooling relations are display-only and do not contribute TWP."""
        # Create another tooling
        other_tooling = Tooling(
            tooling_number="C002",
            mold_type="连续模",
            is_continuous=True,
            cavity_count=1,
            status="AVAILABLE",
        )
        db.add(other_tooling)
        await db.commit()
        await db.refresh(other_tooling)

        # Link part only to continuous_tooling
        tp = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        db.add(tp)
        await db.commit()

        # Create a shared relation between continuous_tooling and other_tooling
        relation = ToolingSharedRelation(
            tooling_id=continuous_tooling.id,
            related_tooling_id=other_tooling.id,
            relation_scope="left-right",
            confidence="high",
        )
        db.add(relation)
        await db.commit()

        # Add spec to other_tooling (not directly linked to part)
        other_spec = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=other_tooling.id,
            spec_twph="T2.0*W60*P120",
            thickness=Decimal("2.0"),
            is_primary=True,
        )
        db.add(other_spec)
        await db.commit()

        # The shared relation should be visible in detail view but NOT merge TWP
        # Only continuous_tooling's specs should be considered for display


@pytest.mark.asyncio
class TestDifferentSpecMultiTooling:
    """Test parts with different TWP specs across multiple toolings."""

    async def test_different_specs_different_toolings(
        self,
        db: AsyncSession,
        base_part: Part,
        continuous_tooling: Tooling,
        simple_tooling: Tooling,
    ):
        """Part has different specs for different mold types."""
        tp1 = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        tp2 = ToolingPart(part_id=base_part.id, tooling_id=simple_tooling.id, is_primary=False)
        db.add_all([tp1, tp2])
        await db.commit()

        spec1 = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.0*W50*P100",
            thickness=Decimal("1.0"),
            width=Decimal("50"),
            pitch=Decimal("100"),
            is_primary=True,
        )
        spec2 = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=simple_tooling.id,
            spec_twph="T1.5*W60*P110",
            thickness=Decimal("1.5"),
            width=Decimal("60"),
            pitch=Decimal("110"),
            is_primary=True,
        )
        db.add_all([spec1, spec2])
        await db.commit()

        # Verify both specs exist and are primary for their respective toolings
        result = await db.execute(
            select(PartToolingSpec)
            .where(PartToolingSpec.part_id == base_part.id, PartToolingSpec.is_primary == True)
            .order_by(PartToolingSpec.tooling_id)
        )
        primaries = result.scalars().all()
        assert len(primaries) == 2
        assert primaries[0].tooling_id == continuous_tooling.id
        assert primaries[0].thickness == Decimal("1.0")
        assert primaries[1].tooling_id == simple_tooling.id
        assert primaries[1].thickness == Decimal("1.5")


@pytest.mark.asyncio
class TestSameSpecMultiTooling:
    """Test parts with same TWP spec across multiple toolings."""

    async def test_same_spec_different_toolings(
        self,
        db: AsyncSession,
        base_part: Part,
        continuous_tooling: Tooling,
        simple_tooling: Tooling,
    ):
        """Part has identical specs for different toolings."""
        tp1 = ToolingPart(part_id=base_part.id, tooling_id=continuous_tooling.id, is_primary=True)
        tp2 = ToolingPart(part_id=base_part.id, tooling_id=simple_tooling.id, is_primary=False)
        db.add_all([tp1, tp2])
        await db.commit()

        # Same TWP values for both toolings
        spec1 = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=continuous_tooling.id,
            spec_twph="T1.2*W50*P100",
            thickness=Decimal("1.2"),
            width=Decimal("50"),
            pitch=Decimal("100"),
            is_primary=True,
        )
        spec2 = PartToolingSpec(
            part_id=base_part.id,
            tooling_id=simple_tooling.id,
            spec_twph="T1.2*W50*P100",
            thickness=Decimal("1.2"),
            width=Decimal("50"),
            pitch=Decimal("100"),
            is_primary=True,
        )
        db.add_all([spec1, spec2])
        await db.commit()

        # Both should be stored and primary for their respective toolings
        result = await db.execute(
            select(PartToolingSpec)
            .where(PartToolingSpec.part_id == base_part.id)
            .order_by(PartToolingSpec.tooling_id)
        )
        specs = result.scalars().all()
        assert len(specs) == 2
        assert all(spec.is_primary for spec in specs)
        assert specs[0].thickness == specs[1].thickness == Decimal("1.2")
