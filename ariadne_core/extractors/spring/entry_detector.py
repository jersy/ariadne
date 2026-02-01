"""Entry point detector for Spring applications."""

from __future__ import annotations

from ariadne_core.models.types import EntryPointData, EntryType


class EntryDetector:
    """从 ASM 分析输出中检测入口点（HTTP API、定时任务、消息消费者）。"""

    def detect_entries(self, classes: list[dict]) -> list[EntryPointData]:
        """从 ASM 分析结果中检测所有入口点。

        Args:
            classes: ASM 分析返回的 classes 数组

        Returns:
            检测到的入口点列表
        """
        entries: list[EntryPointData] = []

        for class_data in classes:
            # 获取类级别的基础路径（用于拼接方法路径）
            class_base_path = class_data.get("classBasePath", "")

            for method in class_data.get("methods", []):
                # HTTP API 入口检测
                if method.get("isRestEndpoint") or method.get("isEntryPoint"):
                    entry_type_str = method.get("entryPointType", "rest_endpoint")

                    if entry_type_str in ("rest_endpoint", "http_api"):
                        http_path = self._build_http_path(class_base_path, method)
                        entries.append(
                            EntryPointData(
                                symbol_fqn=method["fqn"],
                                entry_type=EntryType.HTTP_API,
                                http_method=method.get("httpMethod", "GET"),
                                http_path=http_path,
                            )
                        )

                # 定时任务入口检测
                if method.get("isScheduled"):
                    cron = method.get("scheduledCron") or method.get("attributes", {}).get(
                        "scheduled_cron"
                    )
                    entries.append(
                        EntryPointData(
                            symbol_fqn=method["fqn"],
                            entry_type=EntryType.SCHEDULED,
                            cron_expression=cron,
                        )
                    )

                # MQ 消费者入口检测（通过注解）
                annotations = method.get("annotations", [])
                if isinstance(annotations, list):
                    for ann in annotations:
                        if "RabbitListener" in ann or "KafkaListener" in ann or "JmsListener" in ann:
                            # 尝试从 attributes 提取队列名
                            queue = method.get("attributes", {}).get("queue")
                            entries.append(
                                EntryPointData(
                                    symbol_fqn=method["fqn"],
                                    entry_type=EntryType.MQ_CONSUMER,
                                    mq_queue=queue,
                                )
                            )
                            break

        return entries

    def _build_http_path(self, class_base_path: str, method: dict) -> str:
        """构建完整的 HTTP 路径。

        Args:
            class_base_path: 类级别的基础路径 (如 "/api/users")
            method: 方法数据

        Returns:
            完整的 HTTP 路径
        """
        method_path = method.get("apiPath", "") or method.get("httpPath", "")

        # 如果方法路径已经包含类路径，直接返回
        if method_path.startswith(class_base_path) and class_base_path:
            return method_path

        # 拼接路径
        base = class_base_path.rstrip("/") if class_base_path else ""
        path = method_path.lstrip("/") if method_path else ""

        if base and path:
            return f"{base}/{path}"
        elif base:
            return base
        elif path:
            return f"/{path}"
        else:
            return "/"
