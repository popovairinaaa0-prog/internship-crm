"""Тесты компаний."""

import pytest

from companies.models import Company, HiringStatus
from students.models import Direction


@pytest.mark.django_db
def test_create_company_with_directions():
    py = Direction.objects.create(name="Python", slug="python")

    c = Company.objects.create(
        name="ООО Ромашка",
        website="https://romashka.example",
        hiring_status=HiringStatus.OPEN,
    )
    c.directions.add(py)

    assert c.pk is not None
    assert str(c) == "ООО Ромашка"
    assert list(c.directions.all()) == [py]
    assert list(py.companies.all()) == [c]
