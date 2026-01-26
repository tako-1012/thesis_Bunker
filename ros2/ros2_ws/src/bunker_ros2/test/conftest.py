import pytest


@pytest.fixture(autouse=True)
def call_setups(request):
    """Call legacy `setUp` methods on test instances (for xUnit-style tests).

    Some tests use a `setUp` method without inheriting from
    `unittest.TestCase`. This autouse fixture ensures those setUp
    methods are executed before each test method so tests behave as
    originally intended.
    """
    inst = getattr(request, 'instance', None)
    if inst is None:
        return
    setup = getattr(inst, 'setUp', None)
    if callable(setup):
        setup()
