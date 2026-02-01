"""External dependency analyzer for Spring applications."""

from __future__ import annotations

from ariadne_core.models.types import (
    DependencyStrength,
    DependencyType,
    ExternalDependencyData,
)


class ExternalDependencyAnalyzer:
    """识别外部依赖调用（Redis/MySQL/MQ/HTTP 等）。"""

    # 外部依赖模式匹配
    PATTERNS: dict[DependencyType, list[str]] = {
        DependencyType.REDIS: [
            "org.springframework.data.redis.core.RedisTemplate",
            "org.springframework.data.redis.core.StringRedisTemplate",
            "org.springframework.data.redis.core.ValueOperations",
            "org.springframework.data.redis.core.HashOperations",
            "org.springframework.data.redis.core.ListOperations",
            "org.springframework.data.redis.core.SetOperations",
            "org.springframework.data.redis.core.ZSetOperations",
            "redis.clients.jedis.Jedis",
            "io.lettuce.core.RedisClient",
        ],
        DependencyType.MQ: [
            "org.springframework.amqp.core.AmqpTemplate",
            "org.springframework.amqp.rabbit.core.RabbitTemplate",
            "org.springframework.kafka.core.KafkaTemplate",
            "org.springframework.jms.core.JmsTemplate",
            "com.rabbitmq.client.Channel",
        ],
        DependencyType.HTTP: [
            "org.springframework.web.client.RestTemplate",
            "org.springframework.web.reactive.function.client.WebClient",
            "org.apache.http.client.HttpClient",
            "okhttp3.OkHttpClient",
            "java.net.HttpURLConnection",
        ],
        DependencyType.RPC: [
            "org.apache.dubbo",
            "io.grpc",
            "com.alibaba.dubbo",
        ],
    }

    def analyze(self, classes: list[dict]) -> list[ExternalDependencyData]:
        """分析 ASM 输出，识别外部依赖调用。

        Args:
            classes: ASM 分析返回的 classes 数组

        Returns:
            外部依赖列表
        """
        deps: list[ExternalDependencyData] = []
        seen: set[tuple[str, str, str]] = set()  # 去重: (caller, type, target)

        for class_data in classes:
            for method in class_data.get("methods", []):
                method_fqn = method.get("fqn", "")

                for call in method.get("calls", []):
                    target_fqn = call.get("toFqn", "")

                    # MyBatis 调用（通过 ASM 标记识别）
                    if call.get("isMybatisBaseMapperCall"):
                        key = (method_fqn, "mysql", target_fqn)
                        if key not in seen:
                            seen.add(key)
                            deps.append(
                                ExternalDependencyData(
                                    caller_fqn=method_fqn,
                                    dependency_type=DependencyType.MYSQL,
                                    target=target_fqn,
                                    strength=DependencyStrength.STRONG,
                                )
                            )
                        continue

                    # Mapper 接口调用（通过名称模式识别）
                    if self._is_mapper_call(target_fqn):
                        key = (method_fqn, "mysql", target_fqn)
                        if key not in seen:
                            seen.add(key)
                            deps.append(
                                ExternalDependencyData(
                                    caller_fqn=method_fqn,
                                    dependency_type=DependencyType.MYSQL,
                                    target=target_fqn,
                                    strength=DependencyStrength.STRONG,
                                )
                            )
                        continue

                    # 其他外部依赖（通过模式匹配）
                    dep_type = self._match_pattern(target_fqn)
                    if dep_type:
                        key = (method_fqn, dep_type.value, target_fqn)
                        if key not in seen:
                            seen.add(key)
                            # HTTP 客户端调用视为弱依赖
                            strength = (
                                DependencyStrength.WEAK
                                if dep_type == DependencyType.HTTP
                                else DependencyStrength.STRONG
                            )
                            deps.append(
                                ExternalDependencyData(
                                    caller_fqn=method_fqn,
                                    dependency_type=dep_type,
                                    target=target_fqn,
                                    strength=strength,
                                )
                            )

        return deps

    def _match_pattern(self, fqn: str) -> DependencyType | None:
        """匹配外部依赖模式。"""
        for dep_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                if fqn.startswith(pattern):
                    return dep_type
        return None

    def _is_mapper_call(self, fqn: str) -> bool:
        """检查是否是 MyBatis Mapper 调用。"""
        # 提取类名部分
        if "." not in fqn:
            return False

        # 获取方法所在的类名
        parts = fqn.rsplit(".", 1)
        if len(parts) < 2:
            return False

        class_part = parts[0]
        class_name = class_part.rsplit(".", 1)[-1] if "." in class_part else class_part

        # 常见 Mapper 命名模式
        return (
            class_name.endswith("Mapper")
            or class_name.endswith("Dao")
            or class_name.endswith("Repository")
        ) and not class_name.startswith("Base")
