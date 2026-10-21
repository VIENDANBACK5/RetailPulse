"""Keep optional in-memory extension tests independent of user/runtime state."""
import copy
import pytest


def pytest_collection_modifyitems(items):
    optional = {"test_four_pillars.py", "test_heterogeneous_integration.py", "test_dataops_mlops.py"}
    for item in items:
        if item.path.name in optional:
            item.add_marker(pytest.mark.optional_extension)
        if (item.path.name == "test_etl_acceptance.py" and
                ("PostgreSQLAcceptance" in item.nodeid or "HttpAcceptance" in item.nodeid)):
            item.add_marker(pytest.mark.integration)
        if item.path.name == "test_runtime_and_bi.py" and "test_registry" not in item.name:
            item.add_marker(pytest.mark.integration)
        if item.path.name == "test_web_acceptance.py" and "verified_database" in item.fixturenames:
            item.add_marker(pytest.mark.integration)


@pytest.fixture(autouse=True)
def isolate_optional_broker(request):
    if request.node.path.name not in {"test_four_pillars.py", "test_heterogeneous_integration.py"}:
        yield
        return
    from src.streaming.kafka_engine import broker, KafkaTopic
    from src.streaming.stream_processor import stream_processor
    original_topics = broker.topics
    state = copy.deepcopy(stream_processor.__dict__)
    broker.topics = {name: KafkaTopic(name, topic.num_partitions)
                     for name, topic in original_topics.items()}
    try:
        yield
    finally:
        broker.topics = original_topics
        stream_processor.__dict__.clear()
        stream_processor.__dict__.update(state)
