def test_threads_routes_exist():
    from src.api.routes.threads import router

    paths = [r.path for r in router.routes]
    assert "/threads" in paths
