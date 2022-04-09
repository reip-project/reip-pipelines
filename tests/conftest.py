import pytest
def pytest_runtest_call(item):
    try:
        item.runtest()
    except KeyboardInterrupt as e:
        # try:
            raise RuntimeError(str(e))
        # finally:
        #     pytest.exit("decided to stop the test run")
