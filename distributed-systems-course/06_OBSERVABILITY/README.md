# Module 06: Observability
*Monitoring, logging, and tracing distributed systems*

## Learning Objectives

By the end of this module, you will:
- Implement the three pillars of observability (metrics, logs, traces)
- Design comprehensive monitoring strategies with SLIs/SLOs/SLAs
- Build distributed tracing for request flow visibility
- Create effective alerting and incident response systems
- Apply observability-driven development practices

## Topics Covered

1. **The Three Pillars** - Metrics, Logs, and Traces
2. **Service Level Objectives** - SLIs, SLOs, and Error Budgets  
3. **Distributed Tracing** - Request flow tracking
4. **Application Metrics** - Business and technical metrics
5. **Structured Logging** - Centralized log management
6. **Alerting & Incident Response** - Proactive problem detection

---

## 1. The Three Pillars of Observability

### Metrics: Time-Series Data

```python
import time
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from collections import defaultdict, deque
from enum import Enum

class MetricType(Enum):
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"

@dataclass
class MetricPoint:
    timestamp: float
    value: float
    labels: Dict[str, str]

class Metric:
    """Base metric class"""
    
    def __init__(self, name: str, description: str, labels: Dict[str, str] = None):
        self.name = name
        self.description = description
        self.labels = labels or {}
        self.points: List[MetricPoint] = []
    
    def record(self, value: float, labels: Dict[str, str] = None):
        combined_labels = {**self.labels, **(labels or {})}
        point = MetricPoint(time.time(), value, combined_labels)
        self.points.append(point)
        
        # Keep only recent points (last hour)
        cutoff = time.time() - 3600
        self.points = [p for p in self.points if p.timestamp > cutoff]

class Counter(Metric):
    """Counter metric - always increasing"""
    
    def __init__(self, name: str, description: str, labels: Dict[str, str] = None):
        super().__init__(name, description, labels)
        self.value = 0.0
    
    def inc(self, amount: float = 1.0, labels: Dict[str, str] = None):
        self.value += amount
        self.record(self.value, labels)
    
    def get_value(self) -> float:
        return self.value

class Gauge(Metric):
    """Gauge metric - can go up and down"""
    
    def __init__(self, name: str, description: str, labels: Dict[str, str] = None):
        super().__init__(name, description, labels)
        self.value = 0.0
    
    def set(self, value: float, labels: Dict[str, str] = None):
        self.value = value
        self.record(value, labels)
    
    def inc(self, amount: float = 1.0, labels: Dict[str, str] = None):
        self.value += amount
        self.record(self.value, labels)
    
    def dec(self, amount: float = 1.0, labels: Dict[str, str] = None):
        self.value -= amount
        self.record(self.value, labels)

class Histogram(Metric):
    """Histogram metric - distribution of values"""
    
    def __init__(self, name: str, description: str, 
                 buckets: List[float] = None, labels: Dict[str, str] = None):
        super().__init__(name, description, labels)
        self.buckets = buckets or [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')]
        self.bucket_counts = defaultdict(int)
        self.sum = 0.0
        self.count = 0
    
    def observe(self, value: float, labels: Dict[str, str] = None):
        self.sum += value
        self.count += 1
        
        # Update bucket counts
        for bucket in self.buckets:
            if value <= bucket:
                bucket_key = f"le_{bucket}"
                self.bucket_counts[bucket_key] += 1
        
        self.record(value, labels)
    
    def get_percentile(self, percentile: float) -> float:
        """Calculate percentile from histogram data"""
        if not self.points:
            return 0.0
        
        sorted_values = sorted([p.value for p in self.points])
        index = int(len(sorted_values) * (percentile / 100))
        return sorted_values[min(index, len(sorted_values) - 1)]

class MetricsRegistry:
    """Central registry for all metrics"""
    
    def __init__(self):
        self.metrics: Dict[str, Metric] = {}
        self.exporters: List[MetricsExporter] = []
    
    def counter(self, name: str, description: str, labels: Dict[str, str] = None) -> Counter:
        if name not in self.metrics:
            self.metrics[name] = Counter(name, description, labels)
        return self.metrics[name]
    
    def gauge(self, name: str, description: str, labels: Dict[str, str] = None) -> Gauge:
        if name not in self.metrics:
            self.metrics[name] = Gauge(name, description, labels)
        return self.metrics[name]
    
    def histogram(self, name: str, description: str, 
                 buckets: List[float] = None, labels: Dict[str, str] = None) -> Histogram:
        if name not in self.metrics:
            self.metrics[name] = Histogram(name, description, buckets, labels)
        return self.metrics[name]
    
    def add_exporter(self, exporter: 'MetricsExporter'):
        self.exporters.append(exporter)
    
    async def export_metrics(self):
        """Export metrics to all configured exporters"""
        for exporter in self.exporters:
            try:
                await exporter.export(self.metrics)
            except Exception as e:
                print(f"Failed to export metrics: {e}")

class MetricsExporter:
    """Base class for metric exporters"""
    
    async def export(self, metrics: Dict[str, Metric]):
        raise NotImplementedError

class PrometheusExporter(MetricsExporter):
    """Export metrics in Prometheus format"""
    
    async def export(self, metrics: Dict[str, Metric]) -> str:
        output = []
        
        for metric in metrics.values():
            # Add help and type comments
            output.append(f"# HELP {metric.name} {metric.description}")
            
            if isinstance(metric, Counter):
                output.append(f"# TYPE {metric.name} counter")
                labels_str = self._format_labels(metric.labels)
                output.append(f"{metric.name}{labels_str} {metric.get_value()}")
                
            elif isinstance(metric, Gauge):
                output.append(f"# TYPE {metric.name} gauge")
                labels_str = self._format_labels(metric.labels)
                output.append(f"{metric.name}{labels_str} {metric.value}")
                
            elif isinstance(metric, Histogram):
                output.append(f"# TYPE {metric.name} histogram")
                
                # Export bucket counts
                for bucket, count in metric.bucket_counts.items():
                    bucket_value = bucket.replace("le_", "")
                    labels = {**metric.labels, "le": bucket_value}
                    labels_str = self._format_labels(labels)
                    output.append(f"{metric.name}_bucket{labels_str} {count}")
                
                # Export sum and count
                labels_str = self._format_labels(metric.labels)
                output.append(f"{metric.name}_sum{labels_str} {metric.sum}")
                output.append(f"{metric.name}_count{labels_str} {metric.count}")
        
        return "\n".join(output)
    
    def _format_labels(self, labels: Dict[str, str]) -> str:
        if not labels:
            return ""
        
        label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ",".join(label_pairs) + "}"

# Application Metrics
class ApplicationMetrics:
    """Application-specific metrics for distributed systems"""
    
    def __init__(self):
        self.registry = MetricsRegistry()
        self._setup_standard_metrics()
    
    def _setup_standard_metrics(self):
        """Setup standard application metrics"""
        
        # Request metrics
        self.request_total = self.registry.counter(
            "http_requests_total",
            "Total number of HTTP requests",
            {"service": "order-service"}
        )
        
        self.request_duration = self.registry.histogram(
            "http_request_duration_seconds",
            "Duration of HTTP requests in seconds",
            buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')]
        )
        
        self.request_errors = self.registry.counter(
            "http_request_errors_total",
            "Total number of HTTP request errors"
        )
        
        # Business metrics
        self.orders_total = self.registry.counter(
            "orders_total",
            "Total number of orders created"
        )
        
        self.order_value = self.registry.histogram(
            "order_value_dollars",
            "Distribution of order values in dollars",
            buckets=[10, 25, 50, 100, 250, 500, 1000, float('inf')]
        )
        
        self.active_users = self.registry.gauge(
            "active_users",
            "Number of currently active users"
        )
        
        # Infrastructure metrics
        self.database_connections = self.registry.gauge(
            "database_connections_active",
            "Number of active database connections"
        )
        
        self.cache_hits = self.registry.counter(
            "cache_hits_total",
            "Total number of cache hits"
        )
        
        self.cache_misses = self.registry.counter(
            "cache_misses_total", 
            "Total number of cache misses"
        )

# Metrics Decorator for Automatic Instrumentation
def metrics_instrumented(registry: MetricsRegistry):
    """Decorator to automatically instrument functions with metrics"""
    
    def decorator(func):
        func_name = func.__name__
        
        # Create metrics for this function
        duration_metric = registry.histogram(
            f"{func_name}_duration_seconds",
            f"Duration of {func_name} function calls"
        )
        
        calls_metric = registry.counter(
            f"{func_name}_calls_total",
            f"Total calls to {func_name} function"
        )
        
        errors_metric = registry.counter(
            f"{func_name}_errors_total",
            f"Total errors in {func_name} function"
        )
        
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            calls_metric.inc()
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                errors_metric.inc(labels={"error_type": type(e).__name__})
                raise
            finally:
                duration = time.time() - start_time
                duration_metric.observe(duration)
        
        return wrapper
    
    return decorator

# Example Service with Metrics
class OrderService:
    """Order service with comprehensive metrics"""
    
    def __init__(self):
        self.metrics = ApplicationMetrics()
        
    @metrics_instrumented
    async def create_order(self, order_data: Dict) -> Dict:
        """Create order with automatic metrics collection"""
        
        # Record business metrics
        self.metrics.orders_total.inc(labels={
            "customer_type": order_data.get("customer_type", "regular"),
            "channel": order_data.get("channel", "web")
        })
        
        self.metrics.order_value.observe(
            order_data.get("total_amount", 0),
            labels={"currency": order_data.get("currency", "USD")}
        )
        
        # Simulate order creation
        await asyncio.sleep(0.1)  # Simulate processing time
        
        order_id = f"order_{int(time.time())}"
        return {"order_id": order_id, "status": "created"}
    
    async def get_metrics_endpoint(self) -> str:
        """Endpoint to expose metrics in Prometheus format"""
        exporter = PrometheusExporter()
        return await exporter.export(self.metrics.registry.metrics)
```

---

## 2. Service Level Objectives (SLOs)

### SLI/SLO Implementation Framework

```python
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import time

class SLIType(Enum):
    AVAILABILITY = "availability"
    LATENCY = "latency"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    FRESHNESS = "freshness"

@dataclass
class SLI:
    """Service Level Indicator"""
    name: str
    description: str
    sli_type: SLIType
    query: str  # Query to calculate SLI
    unit: str
    good_events_query: Optional[str] = None
    total_events_query: Optional[str] = None

@dataclass
class SLO:
    """Service Level Objective"""
    name: str
    description: str
    sli: SLI
    target: float  # Target percentage (e.g., 99.9)
    time_window: str  # e.g., "30d", "7d", "1h"
    alerting_threshold: float  # When to alert (e.g., 99.0)

class SLOTracker:
    """Tracks SLO compliance and error budgets"""
    
    def __init__(self):
        self.slos: Dict[str, SLO] = {}
        self.measurements: Dict[str, List[Dict]] = defaultdict(list)
    
    def register_slo(self, slo: SLO):
        """Register a new SLO"""
        self.slos[slo.name] = slo
        self.measurements[slo.name] = []
    
    def record_measurement(self, slo_name: str, value: float, 
                          timestamp: float = None, metadata: Dict = None):
        """Record SLI measurement"""
        if slo_name not in self.slos:
            raise ValueError(f"SLO {slo_name} not registered")
        
        measurement = {
            "timestamp": timestamp or time.time(),
            "value": value,
            "metadata": metadata or {}
        }
        
        self.measurements[slo_name].append(measurement)
        
        # Keep only measurements within time window
        slo = self.slos[slo_name]
        time_window_seconds = self._parse_time_window(slo.time_window)
        cutoff = time.time() - time_window_seconds
        
        self.measurements[slo_name] = [
            m for m in self.measurements[slo_name] 
            if m["timestamp"] > cutoff
        ]
    
    def get_slo_status(self, slo_name: str) -> Dict[str, Any]:
        """Get current SLO status and error budget"""
        if slo_name not in self.slos:
            raise ValueError(f"SLO {slo_name} not registered")
        
        slo = self.slos[slo_name]
        measurements = self.measurements[slo_name]
        
        if not measurements:
            return {
                "slo_name": slo_name,
                "current_sli": None,
                "target": slo.target,
                "compliance": None,
                "error_budget_remaining": None,
                "status": "insufficient_data"
            }
        
        # Calculate current SLI based on type
        current_sli = self._calculate_sli(slo, measurements)
        compliance = (current_sli / slo.target) * 100 if current_sli else 0
        
        # Calculate error budget
        error_budget_total = 100 - slo.target  # e.g., 100 - 99.9 = 0.1%
        error_budget_used = max(0, slo.target - current_sli)
        error_budget_remaining = max(0, error_budget_total - error_budget_used)
        error_budget_percentage = (error_budget_remaining / error_budget_total) * 100 if error_budget_total > 0 else 100
        
        # Determine status
        status = "healthy"
        if current_sli < slo.alerting_threshold:
            status = "alerting"
        elif error_budget_percentage < 10:  # Less than 10% error budget remaining
            status = "warning"
        
        return {
            "slo_name": slo_name,
            "current_sli": current_sli,
            "target": slo.target,
            "compliance": compliance,
            "error_budget_remaining": error_budget_percentage,
            "error_budget_used": (error_budget_used / error_budget_total) * 100 if error_budget_total > 0 else 0,
            "status": status,
            "measurements_count": len(measurements)
        }
    
    def _calculate_sli(self, slo: SLO, measurements: List[Dict]) -> float:
        """Calculate SLI from measurements"""
        if slo.sli.sli_type == SLIType.AVAILABILITY:
            # For availability: percentage of successful requests
            total_requests = len(measurements)
            successful_requests = sum(1 for m in measurements if m["value"] == 1.0)
            return (successful_requests / total_requests) * 100 if total_requests > 0 else 0
        
        elif slo.sli.sli_type == SLIType.LATENCY:
            # For latency: percentage of requests under threshold
            threshold = slo.target / 100  # Convert percentage to decimal
            fast_requests = sum(1 for m in measurements if m["value"] <= threshold)
            return (fast_requests / len(measurements)) * 100 if measurements else 0
        
        elif slo.sli.sli_type == SLIType.ERROR_RATE:
            # For error rate: percentage of requests that are NOT errors
            total_requests = len(measurements) 
            error_requests = sum(1 for m in measurements if m["value"] == 1.0)  # 1.0 = error
            success_rate = ((total_requests - error_requests) / total_requests) * 100 if total_requests > 0 else 0
            return success_rate
        
        else:
            # For other types, use average of measurements
            if not measurements:
                return 0
            return sum(m["value"] for m in measurements) / len(measurements)
    
    def _parse_time_window(self, time_window: str) -> int:
        """Parse time window string to seconds"""
        time_units = {
            's': 1,
            'm': 60,
            'h': 3600,
            'd': 86400,
            'w': 604800
        }
        
        if time_window[-1] in time_units:
            return int(time_window[:-1]) * time_units[time_window[-1]]
        else:
            return int(time_window)  # Assume seconds if no unit

# Comprehensive SLO Configuration
class ServiceSLOConfig:
    """Configuration for service SLOs"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.tracker = SLOTracker()
        self._setup_standard_slos()
    
    def _setup_standard_slos(self):
        """Setup standard SLOs for a web service"""
        
        # Availability SLO
        availability_sli = SLI(
            name=f"{self.service_name}_availability",
            description="Percentage of requests that return successfully",
            sli_type=SLIType.AVAILABILITY,
            query="rate(http_requests_total{job='order-service',code=~'2..'}[5m]) / rate(http_requests_total{job='order-service'}[5m])",
            unit="percentage"
        )
        
        availability_slo = SLO(
            name=f"{self.service_name}_availability_slo",
            description="Order service should be available 99.9% of the time",
            sli=availability_sli,
            target=99.9,
            time_window="30d",
            alerting_threshold=99.0
        )
        
        self.tracker.register_slo(availability_slo)
        
        # Latency SLO
        latency_sli = SLI(
            name=f"{self.service_name}_latency_p99",
            description="99th percentile of request latency",
            sli_type=SLIType.LATENCY,
            query="histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{job='order-service'}[5m]))",
            unit="seconds"
        )
        
        latency_slo = SLO(
            name=f"{self.service_name}_latency_slo",
            description="99% of requests should complete within 500ms",
            sli=latency_sli,
            target=99.0,  # 99% of requests
            time_window="7d",
            alerting_threshold=95.0
        )
        
        self.tracker.register_slo(latency_slo)
        
        # Error Rate SLO
        error_rate_sli = SLI(
            name=f"{self.service_name}_error_rate",
            description="Rate of failed requests",
            sli_type=SLIType.ERROR_RATE,
            query="rate(http_requests_total{job='order-service',code=~'5..'}[5m]) / rate(http_requests_total{job='order-service'}[5m])",
            unit="percentage"
        )
        
        error_rate_slo = SLO(
            name=f"{self.service_name}_error_rate_slo",
            description="Error rate should be below 0.1%",
            sli=error_rate_sli,
            target=99.9,  # 99.9% success rate
            time_window="24h",
            alerting_threshold=99.5
        )
        
        self.tracker.register_slo(error_rate_slo)
    
    def record_request(self, success: bool, duration: float, status_code: int):
        """Record request data for SLO calculations"""
        timestamp = time.time()
        
        # Record availability
        self.tracker.record_measurement(
            f"{self.service_name}_availability_slo",
            1.0 if success else 0.0,
            timestamp,
            {"status_code": status_code}
        )
        
        # Record latency (1.0 if fast enough, 0.0 if too slow)
        latency_threshold = 0.5  # 500ms
        self.tracker.record_measurement(
            f"{self.service_name}_latency_slo", 
            duration,
            timestamp,
            {"fast": duration <= latency_threshold}
        )
        
        # Record error rate (1.0 for error, 0.0 for success)
        self.tracker.record_measurement(
            f"{self.service_name}_error_rate_slo",
            1.0 if not success else 0.0,
            timestamp,
            {"status_code": status_code}
        )
    
    def get_all_slo_status(self) -> Dict[str, Any]:
        """Get status of all SLOs"""
        status = {}
        
        for slo_name in self.tracker.slos.keys():
            status[slo_name] = self.tracker.get_slo_status(slo_name)
        
        return status

# Error Budget Policy
class ErrorBudgetPolicy:
    """Manages error budget policies and enforcement"""
    
    def __init__(self):
        self.policies: Dict[str, Dict] = {}
        
    def set_policy(self, service_name: str, policy: Dict):
        """Set error budget policy for a service"""
        self.policies[service_name] = policy
    
    def should_stop_deployments(self, service_name: str, 
                               error_budget_remaining: float) -> bool:
        """Check if deployments should be stopped due to low error budget"""
        if service_name not in self.policies:
            return False
        
        policy = self.policies[service_name]
        threshold = policy.get("stop_deployments_threshold", 10)  # 10%
        
        return error_budget_remaining < threshold
    
    def get_deployment_policy(self, service_name: str,
                            error_budget_remaining: float) -> str:
        """Get deployment policy based on error budget"""
        if service_name not in self.policies:
            return "normal"
        
        policy = self.policies[service_name]
        
        if error_budget_remaining < policy.get("critical_threshold", 5):
            return "freeze"  # Freeze all deployments
        elif error_budget_remaining < policy.get("warning_threshold", 25):
            return "conservative"  # Only critical fixes
        else:
            return "normal"  # Normal deployment cadence
```

---

## 3. Distributed Tracing

### OpenTelemetry Implementation

```python
import uuid
import time
import asyncio
import json
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from contextlib import asynccontextmanager

class SpanKind(Enum):
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"

@dataclass
class SpanContext:
    trace_id: str
    span_id: str
    parent_span_id: Optional[str] = None
    trace_flags: int = 1  # 1 = sampled
    trace_state: str = ""

@dataclass
class Span:
    name: str
    context: SpanContext
    kind: SpanKind = SpanKind.INTERNAL
    start_time: float = field(default_factory=time.time)
    end_time: Optional[float] = None
    status_code: str = "OK"  # OK, ERROR, TIMEOUT
    status_message: str = ""
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[Dict[str, Any]] = field(default_factory=list)
    links: List[SpanContext] = field(default_factory=list)
    
    def set_attribute(self, key: str, value: Any):
        """Set span attribute"""
        self.attributes[key] = value
    
    def add_event(self, name: str, timestamp: float = None, attributes: Dict[str, Any] = None):
        """Add event to span"""
        event = {
            "name": name,
            "timestamp": timestamp or time.time(),
            "attributes": attributes or {}
        }
        self.events.append(event)
    
    def set_status(self, code: str, message: str = ""):
        """Set span status"""
        self.status_code = code
        self.status_message = message
    
    def finish(self):
        """Finish the span"""
        if self.end_time is None:
            self.end_time = time.time()

class Tracer:
    """Distributed tracer implementation"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.active_spans: Dict[str, Span] = {}
        self.exporters: List['SpanExporter'] = []
        self.sampler = AlwaysSampler()  # Default: sample everything
    
    def start_span(self, name: str, parent_context: Optional[SpanContext] = None,
                   kind: SpanKind = SpanKind.INTERNAL, attributes: Dict[str, Any] = None) -> Span:
        """Start a new span"""
        
        # Generate trace and span IDs
        if parent_context:
            trace_id = parent_context.trace_id
            parent_span_id = parent_context.span_id
        else:
            trace_id = self._generate_trace_id()
            parent_span_id = None
        
        span_id = self._generate_span_id()
        
        # Check if we should sample this trace
        should_sample = self.sampler.should_sample(trace_id, name)
        trace_flags = 1 if should_sample else 0
        
        context = SpanContext(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            trace_flags=trace_flags
        )
        
        span = Span(
            name=name,
            context=context,
            kind=kind,
            attributes=attributes or {}
        )
        
        # Add service information
        span.set_attribute("service.name", self.service_name)
        span.set_attribute("span.kind", kind.value)
        
        self.active_spans[span_id] = span
        return span
    
    def finish_span(self, span: Span):
        """Finish span and export if sampled"""
        span.finish()
        
        if span.context.span_id in self.active_spans:
            del self.active_spans[span.context.span_id]
        
        # Export span if sampled
        if span.context.trace_flags == 1:
            for exporter in self.exporters:
                asyncio.create_task(exporter.export([span]))
    
    def add_exporter(self, exporter: 'SpanExporter'):
        """Add span exporter"""
        self.exporters.append(exporter)
    
    @asynccontextmanager
    async def span(self, name: str, parent_context: Optional[SpanContext] = None,
                   kind: SpanKind = SpanKind.INTERNAL, attributes: Dict[str, Any] = None):
        """Context manager for spans"""
        span = self.start_span(name, parent_context, kind, attributes)
        
        try:
            yield span
        except Exception as e:
            span.set_status("ERROR", str(e))
            span.set_attribute("error", True)
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            raise
        finally:
            self.finish_span(span)
    
    def _generate_trace_id(self) -> str:
        """Generate 128-bit trace ID"""
        return uuid.uuid4().hex + uuid.uuid4().hex[:16]
    
    def _generate_span_id(self) -> str:
        """Generate 64-bit span ID"""
        return uuid.uuid4().hex[:16]

class Sampler:
    """Base sampler class"""
    
    def should_sample(self, trace_id: str, span_name: str) -> bool:
        raise NotImplementedError

class AlwaysSampler(Sampler):
    """Always sample traces"""
    
    def should_sample(self, trace_id: str, span_name: str) -> bool:
        return True

class ProbabilitySampler(Sampler):
    """Sample traces based on probability"""
    
    def __init__(self, probability: float):
        self.probability = probability
    
    def should_sample(self, trace_id: str, span_name: str) -> bool:
        # Use trace_id to ensure consistent sampling decisions
        hash_value = int(trace_id[:8], 16)
        return (hash_value / 0xFFFFFFFF) < self.probability

class RateLimitingSampler(Sampler):
    """Rate-limiting sampler"""
    
    def __init__(self, max_traces_per_second: float):
        self.max_traces_per_second = max_traces_per_second
        self.tokens = max_traces_per_second
        self.last_refill = time.time()
    
    def should_sample(self, trace_id: str, span_name: str) -> bool:
        now = time.time()
        time_passed = now - self.last_refill
        
        # Refill tokens
        self.tokens = min(
            self.max_traces_per_second,
            self.tokens + time_passed * self.max_traces_per_second
        )
        self.last_refill = now
        
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        
        return False

class SpanExporter:
    """Base span exporter"""
    
    async def export(self, spans: List[Span]):
        raise NotImplementedError

class JaegerExporter(SpanExporter):
    """Export spans to Jaeger"""
    
    def __init__(self, endpoint: str = "http://localhost:14268/api/traces"):
        self.endpoint = endpoint
    
    async def export(self, spans: List[Span]):
        """Export spans to Jaeger in Thrift format"""
        jaeger_spans = []
        
        for span in spans:
            jaeger_span = {
                "traceID": span.context.trace_id,
                "spanID": span.context.span_id,
                "parentSpanID": span.context.parent_span_id,
                "operationName": span.name,
                "startTime": int(span.start_time * 1_000_000),  # microseconds
                "duration": int((span.end_time - span.start_time) * 1_000_000) if span.end_time else 0,
                "tags": [
                    {"key": k, "value": v, "type": self._get_tag_type(v)}
                    for k, v in span.attributes.items()
                ],
                "logs": [
                    {
                        "timestamp": int(event["timestamp"] * 1_000_000),
                        "fields": [
                            {"key": "event", "value": event["name"]},
                            *[{"key": k, "value": v} for k, v in event["attributes"].items()]
                        ]
                    }
                    for event in span.events
                ]
            }
            jaeger_spans.append(jaeger_span)
        
        # Send to Jaeger
        payload = {
            "data": [{
                "traceID": spans[0].context.trace_id,
                "spans": jaeger_spans
            }]
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(self.endpoint, json=payload) as response:
                    if response.status != 200:
                        print(f"Failed to export spans: {response.status}")
            except Exception as e:
                print(f"Failed to export spans: {e}")
    
    def _get_tag_type(self, value: Any) -> str:
        """Get Jaeger tag type"""
        if isinstance(value, str):
            return "string"
        elif isinstance(value, bool):
            return "bool"
        elif isinstance(value, (int, float)):
            return "number"
        else:
            return "string"

# Distributed Context Propagation
class TraceContext:
    """Manages trace context across service boundaries"""
    
    @staticmethod
    def inject(span_context: SpanContext, headers: Dict[str, str]):
        """Inject trace context into HTTP headers"""
        headers["traceparent"] = f"00-{span_context.trace_id}-{span_context.span_id}-{span_context.trace_flags:02d}"
        if span_context.trace_state:
            headers["tracestate"] = span_context.trace_state
    
    @staticmethod
    def extract(headers: Dict[str, str]) -> Optional[SpanContext]:
        """Extract trace context from HTTP headers"""
        traceparent = headers.get("traceparent")
        if not traceparent:
            return None
        
        try:
            parts = traceparent.split("-")
            if len(parts) != 4 or parts[0] != "00":
                return None
            
            trace_id = parts[1]
            parent_span_id = parts[2]
            trace_flags = int(parts[3], 16)
            trace_state = headers.get("tracestate", "")
            
            return SpanContext(
                trace_id=trace_id,
                span_id=parent_span_id,  # This will be the parent
                trace_flags=trace_flags,
                trace_state=trace_state
            )
            
        except (ValueError, IndexError):
            return None

# Instrumented HTTP Client
class TracedHTTPClient:
    """HTTP client with automatic tracing"""
    
    def __init__(self, tracer: Tracer):
        self.tracer = tracer
    
    async def request(self, method: str, url: str, headers: Dict[str, str] = None,
                     parent_span: Optional[Span] = None, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with distributed tracing"""
        
        headers = headers or {}
        
        async with self.tracer.span(
            f"HTTP {method} {url}",
            parent_context=parent_span.context if parent_span else None,
            kind=SpanKind.CLIENT,
            attributes={
                "http.method": method,
                "http.url": url,
                "http.scheme": "http" if url.startswith("http://") else "https"
            }
        ) as span:
            
            # Inject trace context
            TraceContext.inject(span.context, headers)
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.request(method, url, headers=headers, **kwargs) as response:
                        
                        # Record HTTP response attributes
                        span.set_attribute("http.status_code", response.status)
                        span.set_attribute("http.response.size", len(await response.read()))
                        
                        if response.status >= 400:
                            span.set_status("ERROR", f"HTTP {response.status}")
                        
                        return await response.json()
                        
            except Exception as e:
                span.set_status("ERROR", str(e))
                raise

# Instrumented Service
class TracedOrderService:
    """Order service with distributed tracing"""
    
    def __init__(self):
        self.tracer = Tracer("order-service")
        self.tracer.add_exporter(JaegerExporter())
        self.http_client = TracedHTTPClient(self.tracer)
        
        # Setup sampling (sample 10% of traces in production)
        self.tracer.sampler = ProbabilitySampler(0.1)
    
    async def create_order(self, order_data: Dict[str, Any],
                          trace_context: Optional[SpanContext] = None) -> Dict[str, Any]:
        """Create order with distributed tracing"""
        
        async with self.tracer.span(
            "create_order",
            parent_context=trace_context,
            kind=SpanKind.SERVER,
            attributes={
                "order.customer_id": order_data.get("customer_id"),
                "order.items_count": len(order_data.get("items", [])),
                "order.total_amount": order_data.get("total_amount")
            }
        ) as span:
            
            span.add_event("order.validation.started")
            
            # Validate order
            await self._validate_order(order_data, span)
            span.add_event("order.validation.completed")
            
            # Check inventory
            span.add_event("inventory.check.started")
            await self._check_inventory(order_data["items"], span)
            span.add_event("inventory.check.completed")
            
            # Process payment
            span.add_event("payment.processing.started")
            payment_result = await self._process_payment(order_data["payment"], span)
            span.add_event("payment.processing.completed")
            
            # Create order record
            order_id = f"order_{int(time.time())}"
            span.set_attribute("order.id", order_id)
            
            return {
                "order_id": order_id,
                "status": "created",
                "payment_id": payment_result["payment_id"]
            }
    
    async def _validate_order(self, order_data: Dict, parent_span: Span):
        """Validate order data"""
        async with self.tracer.span(
            "validate_order",
            parent_context=parent_span.context,
            kind=SpanKind.INTERNAL
        ) as span:
            
            # Validate customer
            customer_id = order_data.get("customer_id")
            if not customer_id:
                raise ValueError("Customer ID is required")
            
            span.set_attribute("validation.customer_id", customer_id)
            
            # Simulate validation
            await asyncio.sleep(0.05)
    
    async def _check_inventory(self, items: List[Dict], parent_span: Span):
        """Check inventory availability"""
        async with self.tracer.span(
            "check_inventory", 
            parent_context=parent_span.context,
            kind=SpanKind.INTERNAL
        ) as span:
            
            span.set_attribute("inventory.items_count", len(items))
            
            # Call inventory service
            inventory_response = await self.http_client.request(
                "POST",
                "http://inventory-service/api/check",
                json={"items": items},
                parent_span=span
            )
            
            if not inventory_response.get("available"):
                raise ValueError("Insufficient inventory")
    
    async def _process_payment(self, payment_data: Dict, parent_span: Span) -> Dict:
        """Process payment"""
        async with self.tracer.span(
            "process_payment",
            parent_context=parent_span.context,
            kind=SpanKind.INTERNAL,
            attributes={
                "payment.method": payment_data.get("method"),
                "payment.amount": payment_data.get("amount")
            }
        ) as span:
            
            # Call payment service
            payment_response = await self.http_client.request(
                "POST",
                "http://payment-service/api/charge",
                json=payment_data,
                parent_span=span
            )
            
            span.set_attribute("payment.transaction_id", payment_response.get("transaction_id"))
            
            return payment_response

# FastAPI Tracing Middleware
from fastapi import FastAPI, Request, Response

class TracingMiddleware:
    """FastAPI middleware for automatic request tracing"""
    
    def __init__(self, tracer: Tracer):
        self.tracer = tracer
    
    async def __call__(self, request: Request, call_next):
        # Extract trace context from headers
        trace_context = TraceContext.extract(dict(request.headers))
        
        # Start span for request
        async with self.tracer.span(
            f"{request.method} {request.url.path}",
            parent_context=trace_context,
            kind=SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.scheme": request.url.scheme,
                "http.user_agent": request.headers.get("user-agent", ""),
                "http.remote_addr": request.client.host if request.client else ""
            }
        ) as span:
            
            # Store span in request state
            request.state.span = span
            
            try:
                response = await call_next(request)
                
                # Add response attributes
                span.set_attribute("http.status_code", response.status_code)
                
                if response.status_code >= 400:
                    span.set_status("ERROR", f"HTTP {response.status_code}")
                
                # Inject trace context into response headers
                response_headers = {}
                TraceContext.inject(span.context, response_headers)
                
                for key, value in response_headers.items():
                    response.headers[key] = value
                
                return response
                
            except Exception as e:
                span.set_status("ERROR", str(e))
                raise

# Setup FastAPI with tracing
def create_traced_app():
    """Create FastAPI app with tracing enabled"""
    
    app = FastAPI(title="Order Service")
    tracer = Tracer("order-service")
    tracer.add_exporter(JaegerExporter())
    
    # Add tracing middleware
    app.middleware("http")(TracingMiddleware(tracer))
    
    order_service = TracedOrderService()
    
    @app.post("/api/orders")
    async def create_order_endpoint(order_data: Dict, request: Request):
        # Get span from middleware
        span = getattr(request.state, "span", None)
        trace_context = span.context if span else None
        
        return await order_service.create_order(order_data, trace_context)
    
    return app
```

---

## 4. Application Metrics

### Golden Signals and Business Metrics

```python
from typing import Dict, List, Any, Optional
import time
from dataclasses import dataclass
from collections import defaultdict

class GoldenSignals:
    """The Four Golden Signals for service monitoring"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics_registry = MetricsRegistry()
        self._setup_golden_signals()
    
    def _setup_golden_signals(self):
        """Setup the four golden signals metrics"""
        
        # 1. Traffic (Request Rate)
        self.request_rate = self.metrics_registry.counter(
            f"{self.service_name}_requests_total",
            "Total number of requests",
            {"service": self.service_name}
        )
        
        # 2. Errors (Error Rate)
        self.error_rate = self.metrics_registry.counter(
            f"{self.service_name}_errors_total", 
            "Total number of errors",
            {"service": self.service_name}
        )
        
        # 3. Latency (Response Time Distribution)
        self.latency = self.metrics_registry.histogram(
            f"{self.service_name}_request_duration_seconds",
            "Request duration in seconds",
            buckets=[0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, float('inf')],
            labels={"service": self.service_name}
        )
        
        # 4. Saturation (Resource Utilization)
        self.cpu_usage = self.metrics_registry.gauge(
            f"{self.service_name}_cpu_usage_percent",
            "CPU usage percentage",
            {"service": self.service_name}
        )
        
        self.memory_usage = self.metrics_registry.gauge(
            f"{self.service_name}_memory_usage_percent",
            "Memory usage percentage", 
            {"service": self.service_name}
        )
        
        self.connection_pool_usage = self.metrics_registry.gauge(
            f"{self.service_name}_connection_pool_usage_percent",
            "Connection pool usage percentage",
            {"service": self.service_name}
        )
    
    def record_request(self, duration: float, success: bool, 
                      status_code: int, method: str, endpoint: str):
        """Record request metrics"""
        labels = {
            "method": method,
            "endpoint": endpoint,
            "status_code": str(status_code)
        }
        
        # Traffic
        self.request_rate.inc(labels=labels)
        
        # Latency
        self.latency.observe(duration, labels=labels)
        
        # Errors
        if not success or status_code >= 400:
            error_labels = {**labels, "error_type": self._classify_error(status_code)}
            self.error_rate.inc(labels=error_labels)
    
    def update_saturation_metrics(self, cpu_percent: float, memory_percent: float,
                                 connection_pool_percent: float):
        """Update saturation metrics"""
        self.cpu_usage.set(cpu_percent)
        self.memory_usage.set(memory_percent)
        self.connection_pool_usage.set(connection_pool_percent)
    
    def _classify_error(self, status_code: int) -> str:
        """Classify error type based on status code"""
        if 400 <= status_code < 500:
            return "client_error"
        elif 500 <= status_code < 600:
            return "server_error"
        else:
            return "unknown_error"

class BusinessMetrics:
    """Business-specific metrics for e-commerce"""
    
    def __init__(self):
        self.registry = MetricsRegistry()
        self._setup_business_metrics()
    
    def _setup_business_metrics(self):
        """Setup business-specific metrics"""
        
        # Revenue metrics
        self.revenue_total = self.registry.counter(
            "revenue_total_dollars",
            "Total revenue in dollars"
        )
        
        self.order_value_distribution = self.registry.histogram(
            "order_value_dollars",
            "Distribution of order values",
            buckets=[5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, float('inf')]
        )
        
        # User engagement metrics
        self.active_users = self.registry.gauge(
            "active_users_current",
            "Currently active users"
        )
        
        self.session_duration = self.registry.histogram(
            "user_session_duration_seconds",
            "User session duration",
            buckets=[30, 60, 300, 900, 1800, 3600, 7200, float('inf')]
        )
        
        # Product metrics
        self.products_viewed = self.registry.counter(
            "products_viewed_total",
            "Total product views"
        )
        
        self.cart_additions = self.registry.counter(
            "cart_additions_total",
            "Total items added to cart"
        )
        
        self.cart_abandonments = self.registry.counter(
            "cart_abandonments_total", 
            "Total cart abandonments"
        )
        
        # Conversion funnel metrics
        self.funnel_step = self.registry.counter(
            "conversion_funnel_step_total",
            "Users reaching each funnel step"
        )
        
        # Inventory metrics
        self.out_of_stock_events = self.registry.counter(
            "out_of_stock_events_total",
            "Products going out of stock"
        )
        
        self.low_inventory_products = self.registry.gauge(
            "low_inventory_products_count",
            "Number of products with low inventory"
        )
    
    def record_order(self, order_value: float, currency: str, 
                    customer_type: str, channel: str):
        """Record order business metrics"""
        labels = {
            "currency": currency,
            "customer_type": customer_type,
            "channel": channel
        }
        
        self.revenue_total.inc(order_value, labels=labels)
        self.order_value_distribution.observe(order_value, labels=labels)
    
    def record_user_activity(self, user_id: str, activity: str, 
                           product_id: Optional[str] = None):
        """Record user activity metrics"""
        if activity == "product_view":
            self.products_viewed.inc(labels={"product_id": product_id or "unknown"})
        elif activity == "cart_add":
            self.cart_additions.inc(labels={"product_id": product_id or "unknown"})
        elif activity == "cart_abandon":
            self.cart_abandonments.inc(labels={"reason": "timeout"})
    
    def record_funnel_step(self, step: str, user_type: str = "anonymous"):
        """Record conversion funnel progression"""
        labels = {"step": step, "user_type": user_type}
        self.funnel_step.inc(labels=labels)
    
    def update_inventory_metrics(self, out_of_stock_count: int, 
                               low_inventory_count: int):
        """Update inventory-related metrics"""
        self.low_inventory_products.set(low_inventory_count)
        # out_of_stock_events is incremented when products go out of stock

# RED/USE Method Implementation
class REDMetrics:
    """Rate, Errors, Duration metrics (for request-driven services)"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.registry = MetricsRegistry()
        self._setup_red_metrics()
    
    def _setup_red_metrics(self):
        """Setup RED metrics"""
        
        # Rate
        self.request_rate = self.registry.counter(
            f"{self.service_name}_requests_per_second",
            "Requests per second"
        )
        
        # Errors 
        self.error_rate = self.registry.counter(
            f"{self.service_name}_error_rate",
            "Error rate"
        )
        
        # Duration
        self.response_time = self.registry.histogram(
            f"{self.service_name}_response_time_seconds",
            "Response time in seconds"
        )

class USEMetrics:
    """Utilization, Saturation, Errors metrics (for resource-oriented services)"""
    
    def __init__(self, resource_name: str):
        self.resource_name = resource_name
        self.registry = MetricsRegistry()
        self._setup_use_metrics()
    
    def _setup_use_metrics(self):
        """Setup USE metrics"""
        
        # Utilization
        self.utilization = self.registry.gauge(
            f"{self.resource_name}_utilization_percent",
            f"{self.resource_name} utilization percentage"
        )
        
        # Saturation
        self.saturation = self.registry.gauge(
            f"{self.resource_name}_saturation_percent",
            f"{self.resource_name} saturation percentage"
        )
        
        # Errors
        self.errors = self.registry.counter(
            f"{self.resource_name}_errors_total",
            f"{self.resource_name} errors"
        )

# Comprehensive Metrics Dashboard Data
class MetricsDashboard:
    """Provides data for monitoring dashboards"""
    
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.golden_signals = GoldenSignals(service_name)
        self.business_metrics = BusinessMetrics()
        self.red_metrics = REDMetrics(service_name)
        
    def get_service_health_summary(self) -> Dict[str, Any]:
        """Get overall service health summary"""
        return {
            "service": self.service_name,
            "timestamp": time.time(),
            "traffic": {
                "requests_per_minute": self._calculate_rate("requests_total", 60),
                "errors_per_minute": self._calculate_rate("errors_total", 60)
            },
            "latency": {
                "p50": self._get_percentile("request_duration", 50),
                "p95": self._get_percentile("request_duration", 95),
                "p99": self._get_percentile("request_duration", 99)
            },
            "saturation": {
                "cpu_usage": self.golden_signals.cpu_usage.value,
                "memory_usage": self.golden_signals.memory_usage.value,
                "connection_pool_usage": self.golden_signals.connection_pool_usage.value
            }
        }
    
    def get_business_kpis(self) -> Dict[str, Any]:
        """Get business KPI summary"""
        return {
            "revenue": {
                "total_today": self._get_daily_total("revenue_total"),
                "average_order_value": self._get_average_order_value(),
            },
            "users": {
                "active_now": self.business_metrics.active_users.value,
                "new_signups_today": self._get_daily_total("user_signups"),
            },
            "conversion": {
                "cart_conversion_rate": self._calculate_conversion_rate(),
                "revenue_per_visitor": self._calculate_revenue_per_visitor()
            }
        }
    
    def _calculate_rate(self, metric_name: str, window_seconds: int) -> float:
        """Calculate rate over time window"""
        # In real implementation, this would query time-series data
        # For demo, return simulated value
        return 42.0
    
    def _get_percentile(self, metric_name: str, percentile: int) -> float:
        """Get percentile from histogram"""
        # In real implementation, this would calculate from histogram data
        return 0.15  # 150ms
    
    def _get_daily_total(self, metric_name: str) -> float:
        """Get daily total for counter metric"""
        # Query from time-series database
        return 1250.0
    
    def _get_average_order_value(self) -> float:
        """Calculate average order value"""
        # total_revenue / total_orders
        return 75.50
    
    def _calculate_conversion_rate(self) -> float:
        """Calculate cart to order conversion rate"""
        # orders / cart_additions
        return 15.2  # 15.2%
    
    def _calculate_revenue_per_visitor(self) -> float:
        """Calculate revenue per visitor"""
        # total_revenue / unique_visitors
        return 12.75

# Alerting Rules Engine
@dataclass
class AlertRule:
    name: str
    description: str
    metric_query: str
    threshold: float
    comparison: str  # "gt", "lt", "eq"
    duration: int   # seconds
    severity: str   # "critical", "warning", "info"
    labels: Dict[str, str] = None

class AlertingEngine:
    """Simple alerting engine for metrics"""
    
    def __init__(self):
        self.rules: List[AlertRule] = []
        self.active_alerts: Dict[str, Dict] = {}
        self.alert_handlers: List[Callable] = []
    
    def add_rule(self, rule: AlertRule):
        """Add alerting rule"""
        self.rules.append(rule)
    
    def add_alert_handler(self, handler: Callable):
        """Add alert handler (e.g., send to Slack, PagerDuty)"""
        self.alert_handlers.append(handler)
    
    async def evaluate_rules(self, metrics: Dict[str, Any]):
        """Evaluate all alerting rules against current metrics"""
        
        for rule in self.rules:
            try:
                current_value = self._evaluate_metric_query(rule.metric_query, metrics)
                should_alert = self._compare_value(current_value, rule.threshold, rule.comparison)
                
                alert_key = f"{rule.name}_{rule.metric_query}"
                
                if should_alert:
                    if alert_key not in self.active_alerts:
                        # New alert
                        alert = {
                            "rule": rule,
                            "current_value": current_value,
                            "started_at": time.time(),
                            "labels": rule.labels or {}
                        }
                        
                        self.active_alerts[alert_key] = alert
                        await self._fire_alert(alert)
                    
                else:
                    if alert_key in self.active_alerts:
                        # Alert resolved
                        alert = self.active_alerts.pop(alert_key)
                        await self._resolve_alert(alert, current_value)
                        
            except Exception as e:
                print(f"Error evaluating rule {rule.name}: {e}")
    
    def _evaluate_metric_query(self, query: str, metrics: Dict[str, Any]) -> float:
        """Evaluate metric query (simplified)"""
        # In real implementation, this would parse and execute the query
        # For demo, return a simulated value based on query
        if "error_rate" in query:
            return 2.5  # 2.5% error rate
        elif "response_time" in query:
            return 0.25  # 250ms
        elif "cpu_usage" in query:
            return 85.0  # 85% CPU
        else:
            return 0.0
    
    def _compare_value(self, current: float, threshold: float, comparison: str) -> bool:
        """Compare current value with threshold"""
        if comparison == "gt":
            return current > threshold
        elif comparison == "lt":
            return current < threshold
        elif comparison == "eq":
            return abs(current - threshold) < 0.01  # Approximate equality
        else:
            return False
    
    async def _fire_alert(self, alert: Dict):
        """Fire new alert"""
        rule = alert["rule"]
        message = f"🚨 {rule.severity.upper()}: {rule.name}\n" \
                 f"Description: {rule.description}\n" \
                 f"Current value: {alert['current_value']}\n" \
                 f"Threshold: {rule.threshold}"
        
        for handler in self.alert_handlers:
            try:
                await handler("fire", message, alert)
            except Exception as e:
                print(f"Alert handler failed: {e}")
    
    async def _resolve_alert(self, alert: Dict, current_value: float):
        """Resolve alert"""
        rule = alert["rule"]
        duration = time.time() - alert["started_at"]
        
        message = f"✅ RESOLVED: {rule.name}\n" \
                 f"Current value: {current_value}\n" \
                 f"Duration: {duration:.0f} seconds"
        
        for handler in self.alert_handlers:
            try:
                await handler("resolve", message, alert)
            except Exception as e:
                print(f"Alert handler failed: {e}")

# Setup standard alerting rules
def setup_standard_alerts(service_name: str) -> AlertingEngine:
    """Setup standard alerting rules for a service"""
    
    engine = AlertingEngine()
    
    # High error rate
    engine.add_rule(AlertRule(
        name=f"{service_name}_high_error_rate",
        description="Service error rate is above acceptable threshold",
        metric_query=f"rate({service_name}_errors_total[5m]) / rate({service_name}_requests_total[5m]) * 100",
        threshold=5.0,  # 5%
        comparison="gt",
        duration=300,   # 5 minutes
        severity="critical"
    ))
    
    # High latency
    engine.add_rule(AlertRule(
        name=f"{service_name}_high_latency",
        description="Service latency P95 is above acceptable threshold",
        metric_query=f"histogram_quantile(0.95, {service_name}_request_duration_seconds)",
        threshold=1.0,  # 1 second
        comparison="gt", 
        duration=600,   # 10 minutes
        severity="warning"
    ))
    
    # High CPU usage
    engine.add_rule(AlertRule(
        name=f"{service_name}_high_cpu",
        description="Service CPU usage is high",
        metric_query=f"{service_name}_cpu_usage_percent",
        threshold=80.0,  # 80%
        comparison="gt",
        duration=900,    # 15 minutes
        severity="warning"
    ))
    
    return engine
```

---

## Labs and Projects

### Lab 1: Metrics Implementation
Implement comprehensive metrics collection for a microservice including golden signals and business KPIs.

### Lab 2: Distributed Tracing
Set up end-to-end distributed tracing across multiple services with OpenTelemetry.

### Lab 3: SLO Monitoring
Define and implement SLIs/SLOs for a service with error budget tracking.

### Lab 4: Alerting System
Build an alerting system with multiple notification channels and escalation policies.

## Assessment

### Observability Architecture Design
Design and implement a complete observability strategy for a distributed e-commerce platform:

1. **Metrics Strategy**: Define golden signals, business KPIs, and SLIs/SLOs
2. **Tracing Implementation**: Implement distributed tracing with sampling strategies  
3. **Logging Architecture**: Design structured logging with centralized collection
4. **Dashboard Design**: Create operational and business dashboards
5. **Alerting Strategy**: Define alerting rules and incident response procedures

## References

### Essential Reading
- "Observability Engineering" by Charity Majors, Liz Fong-Jones, George Miranda
- "Site Reliability Engineering" by Google SRE Team
- "The Site Reliability Workbook" by Google SRE Team

### Tools and Platforms
- [Prometheus](https://prometheus.io/) - Metrics collection and alerting
- [Jaeger](https://www.jaegertracing.io/) - Distributed tracing
- [Grafana](https://grafana.com/) - Visualization and dashboards
- [OpenTelemetry](https://opentelemetry.io/) - Observability framework

---

*Next: [Module 07 - Security](../07_SECURITY/)*