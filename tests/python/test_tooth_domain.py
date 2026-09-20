import pytest

from domain.tooth.models import Tooth, is_valid_fdi_number


def test_valid_fdi_numbers() -> None:
    assert is_valid_fdi_number(11)
    assert is_valid_fdi_number(48)
    assert not is_valid_fdi_number(10)
    assert not is_valid_fdi_number(50)


def test_tooth_arch_and_quadrant() -> None:
    upper_right = Tooth(fdi_number=11)
    lower_left = Tooth(fdi_number=34)
    assert upper_right.arch == "upper"
    assert upper_right.quadrant == 1
    assert lower_left.arch == "lower"
    assert lower_left.quadrant == 3


def test_invalid_tooth_number_raises() -> None:
    with pytest.raises(ValueError):
        Tooth(fdi_number=99)
