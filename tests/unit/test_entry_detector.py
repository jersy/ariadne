"""Unit tests for EntryDetector."""

import pytest

from ariadne_core.extractors.spring.entry_detector import EntryDetector
from ariadne_core.models.types import EntryType


@pytest.fixture
def detector():
    return EntryDetector()


class TestHttpApiDetection:
    def test_detect_rest_endpoint(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.UserController",
                "classBasePath": "/api/users",
                "methods": [
                    {
                        "fqn": "com.example.UserController.getUser(Long)",
                        "isRestEndpoint": True,
                        "httpMethod": "GET",
                        "apiPath": "/{id}",
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert len(entries) == 1
        assert entries[0].entry_type == EntryType.HTTP_API
        assert entries[0].http_method == "GET"
        assert entries[0].http_path == "/api/users/{id}"
        assert entries[0].symbol_fqn == "com.example.UserController.getUser(Long)"

    def test_detect_entry_point_type(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.OrderController",
                "classBasePath": "/api/orders",
                "methods": [
                    {
                        "fqn": "com.example.OrderController.createOrder(OrderDTO)",
                        "isEntryPoint": True,
                        "entryPointType": "rest_endpoint",
                        "httpMethod": "POST",
                        "apiPath": "",
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert len(entries) == 1
        assert entries[0].entry_type == EntryType.HTTP_API
        assert entries[0].http_method == "POST"
        assert entries[0].http_path == "/api/orders"

    def test_detect_multiple_endpoints(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.ProductController",
                "classBasePath": "/api/products",
                "methods": [
                    {
                        "fqn": "com.example.ProductController.list()",
                        "isRestEndpoint": True,
                        "httpMethod": "GET",
                        "apiPath": "",
                    },
                    {
                        "fqn": "com.example.ProductController.create(ProductDTO)",
                        "isRestEndpoint": True,
                        "httpMethod": "POST",
                        "apiPath": "",
                    },
                    {
                        "fqn": "com.example.ProductController.update(Long, ProductDTO)",
                        "isRestEndpoint": True,
                        "httpMethod": "PUT",
                        "apiPath": "/{id}",
                    },
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert len(entries) == 3
        methods = {e.http_method for e in entries}
        assert methods == {"GET", "POST", "PUT"}


class TestScheduledDetection:
    def test_detect_scheduled_task(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.ScheduledTasks",
                "methods": [
                    {
                        "fqn": "com.example.ScheduledTasks.cleanup()",
                        "isScheduled": True,
                        "scheduledCron": "0 0 2 * * ?",
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert len(entries) == 1
        assert entries[0].entry_type == EntryType.SCHEDULED
        assert entries[0].cron_expression == "0 0 2 * * ?"
        assert entries[0].symbol_fqn == "com.example.ScheduledTasks.cleanup()"

    def test_detect_scheduled_without_cron(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.Tasks",
                "methods": [
                    {
                        "fqn": "com.example.Tasks.ping()",
                        "isScheduled": True,
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert len(entries) == 1
        assert entries[0].entry_type == EntryType.SCHEDULED
        assert entries[0].cron_expression is None


class TestMqConsumerDetection:
    def test_detect_rabbit_listener(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.OrderListener",
                "methods": [
                    {
                        "fqn": "com.example.OrderListener.handleOrder(OrderMessage)",
                        "annotations": ["@RabbitListener"],
                        "attributes": {"queue": "order-queue"},
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert len(entries) == 1
        assert entries[0].entry_type == EntryType.MQ_CONSUMER
        assert entries[0].mq_queue == "order-queue"

    def test_detect_kafka_listener(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.EventConsumer",
                "methods": [
                    {
                        "fqn": "com.example.EventConsumer.consume(Event)",
                        "annotations": ["@KafkaListener"],
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert len(entries) == 1
        assert entries[0].entry_type == EntryType.MQ_CONSUMER


class TestMixedDetection:
    def test_detect_all_entry_types(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.ApiController",
                "classBasePath": "/api",
                "methods": [
                    {
                        "fqn": "com.example.ApiController.get()",
                        "isRestEndpoint": True,
                        "httpMethod": "GET",
                        "apiPath": "/data",
                    }
                ],
            },
            {
                "fqn": "com.example.Scheduler",
                "methods": [
                    {
                        "fqn": "com.example.Scheduler.run()",
                        "isScheduled": True,
                        "scheduledCron": "0 */5 * * * ?",
                    }
                ],
            },
            {
                "fqn": "com.example.Consumer",
                "methods": [
                    {
                        "fqn": "com.example.Consumer.handle(Message)",
                        "annotations": ["@JmsListener"],
                    }
                ],
            },
        ]

        entries = detector.detect_entries(classes)

        assert len(entries) == 3
        types = {e.entry_type for e in entries}
        assert types == {EntryType.HTTP_API, EntryType.SCHEDULED, EntryType.MQ_CONSUMER}

    def test_empty_classes(self, detector: EntryDetector):
        entries = detector.detect_entries([])
        assert len(entries) == 0

    def test_no_entry_points(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.Service",
                "methods": [
                    {
                        "fqn": "com.example.Service.process()",
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)
        assert len(entries) == 0


class TestHttpPathBuilding:
    def test_build_path_with_base_and_method(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.Controller",
                "classBasePath": "/api/v1",
                "methods": [
                    {
                        "fqn": "com.example.Controller.action()",
                        "isRestEndpoint": True,
                        "httpMethod": "GET",
                        "apiPath": "/action",
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert entries[0].http_path == "/api/v1/action"

    def test_build_path_base_only(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.Controller",
                "classBasePath": "/api/v1",
                "methods": [
                    {
                        "fqn": "com.example.Controller.index()",
                        "isRestEndpoint": True,
                        "httpMethod": "GET",
                        "apiPath": "",
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert entries[0].http_path == "/api/v1"

    def test_build_path_method_only(self, detector: EntryDetector):
        classes = [
            {
                "fqn": "com.example.Controller",
                "classBasePath": "",
                "methods": [
                    {
                        "fqn": "com.example.Controller.health()",
                        "isRestEndpoint": True,
                        "httpMethod": "GET",
                        "apiPath": "/health",
                    }
                ],
            }
        ]

        entries = detector.detect_entries(classes)

        assert entries[0].http_path == "/health"
