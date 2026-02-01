"""Unit tests for ExternalDependencyAnalyzer."""

import pytest

from ariadne_core.extractors.spring.dependency_analyzer import ExternalDependencyAnalyzer
from ariadne_core.models.types import DependencyStrength, DependencyType


@pytest.fixture
def analyzer():
    return ExternalDependencyAnalyzer()


class TestMySqlDetection:
    def test_detect_mybatis_call(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.UserService",
                "methods": [
                    {
                        "fqn": "com.example.UserService.getUser(Long)",
                        "calls": [
                            {
                                "toFqn": "com.example.mapper.UserMapper.selectById(Long)",
                                "isMybatisBaseMapperCall": True,
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.MYSQL
        assert deps[0].strength == DependencyStrength.STRONG
        assert deps[0].target == "com.example.mapper.UserMapper.selectById(Long)"
        assert deps[0].caller_fqn == "com.example.UserService.getUser(Long)"

    def test_detect_mapper_by_name(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.OrderService",
                "methods": [
                    {
                        "fqn": "com.example.OrderService.createOrder(OrderDTO)",
                        "calls": [
                            {
                                "toFqn": "com.example.mapper.OrderMapper.insert(Order)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.MYSQL

    def test_detect_dao_by_name(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.Service",
                "methods": [
                    {
                        "fqn": "com.example.Service.save()",
                        "calls": [
                            {
                                "toFqn": "com.example.dao.UserDao.save(User)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.MYSQL

    def test_detect_repository_by_name(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.Service",
                "methods": [
                    {
                        "fqn": "com.example.Service.find()",
                        "calls": [
                            {
                                "toFqn": "com.example.repository.UserRepository.findById(Long)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.MYSQL

    def test_exclude_base_mapper(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.Service",
                "methods": [
                    {
                        "fqn": "com.example.Service.save()",
                        "calls": [
                            {
                                "toFqn": "com.baomidou.mybatisplus.core.mapper.BaseMapper.insert(Object)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        # BaseMapper should be excluded
        assert len(deps) == 0


class TestRedisDetection:
    def test_detect_redis_template(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.CacheService",
                "methods": [
                    {
                        "fqn": "com.example.CacheService.get(String)",
                        "calls": [
                            {
                                "toFqn": "org.springframework.data.redis.core.RedisTemplate.opsForValue()",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.REDIS
        assert deps[0].strength == DependencyStrength.STRONG

    def test_detect_string_redis_template(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.CacheService",
                "methods": [
                    {
                        "fqn": "com.example.CacheService.set(String, String)",
                        "calls": [
                            {
                                "toFqn": "org.springframework.data.redis.core.StringRedisTemplate.opsForValue()",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.REDIS

    def test_detect_value_operations(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.CacheService",
                "methods": [
                    {
                        "fqn": "com.example.CacheService.get(String)",
                        "calls": [
                            {
                                "toFqn": "org.springframework.data.redis.core.ValueOperations.get(Object)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.REDIS


class TestMqDetection:
    def test_detect_rabbit_template(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.MessageSender",
                "methods": [
                    {
                        "fqn": "com.example.MessageSender.send(Object)",
                        "calls": [
                            {
                                "toFqn": "org.springframework.amqp.rabbit.core.RabbitTemplate.convertAndSend(String, Object)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.MQ
        assert deps[0].strength == DependencyStrength.STRONG

    def test_detect_kafka_template(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.Producer",
                "methods": [
                    {
                        "fqn": "com.example.Producer.publish(Event)",
                        "calls": [
                            {
                                "toFqn": "org.springframework.kafka.core.KafkaTemplate.send(String, Object)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.MQ

    def test_detect_amqp_template(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.Publisher",
                "methods": [
                    {
                        "fqn": "com.example.Publisher.send()",
                        "calls": [
                            {
                                "toFqn": "org.springframework.amqp.core.AmqpTemplate.convertAndSend(Object)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.MQ


class TestHttpDetection:
    def test_detect_rest_template(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.ApiClient",
                "methods": [
                    {
                        "fqn": "com.example.ApiClient.fetchData()",
                        "calls": [
                            {
                                "toFqn": "org.springframework.web.client.RestTemplate.getForObject(String, Class)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.HTTP
        # HTTP is weak dependency
        assert deps[0].strength == DependencyStrength.WEAK

    def test_detect_webclient(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.ReactiveClient",
                "methods": [
                    {
                        "fqn": "com.example.ReactiveClient.fetch()",
                        "calls": [
                            {
                                "toFqn": "org.springframework.web.reactive.function.client.WebClient.get()",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.HTTP
        assert deps[0].strength == DependencyStrength.WEAK


class TestRpcDetection:
    def test_detect_dubbo(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.RpcClient",
                "methods": [
                    {
                        "fqn": "com.example.RpcClient.call()",
                        "calls": [
                            {
                                "toFqn": "org.apache.dubbo.rpc.Invoker.invoke(Invocation)",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 1
        assert deps[0].dependency_type == DependencyType.RPC
        assert deps[0].strength == DependencyStrength.STRONG


class TestDeduplication:
    def test_deduplicate_same_call(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.Service",
                "methods": [
                    {
                        "fqn": "com.example.Service.method1()",
                        "calls": [
                            {
                                "toFqn": "com.example.mapper.UserMapper.selectById(Long)",
                            }
                        ],
                    },
                    {
                        "fqn": "com.example.Service.method2()",
                        "calls": [
                            {
                                "toFqn": "com.example.mapper.UserMapper.selectById(Long)",
                            }
                        ],
                    },
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        # Two different callers, so 2 dependencies
        assert len(deps) == 2

    def test_deduplicate_exact_duplicate(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.Service",
                "methods": [
                    {
                        "fqn": "com.example.Service.method()",
                        "calls": [
                            {
                                "toFqn": "com.example.mapper.UserMapper.selectById(Long)",
                            },
                            # Duplicate call in same method
                            {
                                "toFqn": "com.example.mapper.UserMapper.selectById(Long)",
                            },
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        # Same caller+target+type should be deduplicated
        assert len(deps) == 1


class TestMixedDependencies:
    def test_detect_multiple_types(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.ComplexService",
                "methods": [
                    {
                        "fqn": "com.example.ComplexService.process()",
                        "calls": [
                            {
                                "toFqn": "com.example.mapper.DataMapper.insert(Data)",
                                "isMybatisBaseMapperCall": True,
                            },
                            {
                                "toFqn": "org.springframework.data.redis.core.RedisTemplate.opsForValue()",
                            },
                            {
                                "toFqn": "org.springframework.amqp.rabbit.core.RabbitTemplate.send(Object)",
                            },
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)

        assert len(deps) == 3
        types = {d.dependency_type for d in deps}
        assert types == {DependencyType.MYSQL, DependencyType.REDIS, DependencyType.MQ}

    def test_empty_classes(self, analyzer: ExternalDependencyAnalyzer):
        deps = analyzer.analyze([])
        assert len(deps) == 0

    def test_no_external_dependencies(self, analyzer: ExternalDependencyAnalyzer):
        classes = [
            {
                "fqn": "com.example.Service",
                "methods": [
                    {
                        "fqn": "com.example.Service.process()",
                        "calls": [
                            {
                                "toFqn": "com.example.util.Helper.help()",
                            }
                        ],
                    }
                ],
            }
        ]

        deps = analyzer.analyze(classes)
        assert len(deps) == 0
