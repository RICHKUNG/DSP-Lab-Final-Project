"""
EventBus 單元測試
驗證 pub/sub、執行緒安全、延遲
"""

import sys
import time
import threading
from pathlib import Path

# 加入 src 路徑
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from event_bus import EventBus, EventType, Event


def test_singleton():
    """測試 Singleton 模式"""
    EventBus.reset_instance()

    bus1 = EventBus()
    bus2 = EventBus()
    assert bus1 is bus2, "EventBus 應為 Singleton"
    print("[PASS] Singleton 測試通過")

    EventBus.reset_instance()


def test_pubsub():
    """測試基本的發布/訂閱"""
    EventBus.reset_instance()
    bus = EventBus()
    received = []

    def callback(event: Event):
        received.append(event)

    bus.subscribe(EventType.VOICE_COMMAND, callback)
    bus.start()

    # 發布事件
    bus.publish(Event(EventType.VOICE_COMMAND, {'action': 'JUMP'}))
    time.sleep(0.1)  # 等待分發

    assert len(received) == 1, f"應收到 1 個事件，實際收到 {len(received)}"
    assert received[0].data['action'] == 'JUMP'
    print("[PASS] 基本 pub/sub 測試通過")

    bus.stop()
    EventBus.reset_instance()


def test_multiple_subscribers():
    """測試多個訂閱者"""
    EventBus.reset_instance()
    bus = EventBus()
    results = {'a': [], 'b': []}

    def callback_a(event: Event):
        results['a'].append(event)

    def callback_b(event: Event):
        results['b'].append(event)

    bus.subscribe(EventType.ECG_PEAK, callback_a)
    bus.subscribe(EventType.ECG_PEAK, callback_b)
    bus.start()

    bus.publish(Event(EventType.ECG_PEAK, {'value': 100}))
    time.sleep(0.1)

    assert len(results['a']) == 1, "訂閱者 A 應收到事件"
    assert len(results['b']) == 1, "訂閱者 B 應收到事件"
    print("[PASS] 多訂閱者測試通過")

    bus.stop()
    EventBus.reset_instance()


def test_event_filtering():
    """測試事件過濾（只收到訂閱的類型）"""
    EventBus.reset_instance()
    bus = EventBus()
    received = []

    def callback(event: Event):
        received.append(event)

    bus.subscribe(EventType.VOICE_COMMAND, callback)
    bus.start()

    # 發布不同類型的事件
    bus.publish(Event(EventType.VOICE_COMMAND, {'action': 'JUMP'}))
    bus.publish(Event(EventType.ECG_PEAK, {'value': 100}))  # 不應收到
    bus.publish(Event(EventType.VOICE_COMMAND, {'action': 'START'}))
    time.sleep(0.1)

    assert len(received) == 2, f"應只收到 2 個 VOICE_COMMAND，實際 {len(received)}"
    print("[PASS] 事件過濾測試通過")

    bus.stop()
    EventBus.reset_instance()


def test_thread_safety():
    """測試執行緒安全"""
    EventBus.reset_instance()
    bus = EventBus()
    received = []
    lock = threading.Lock()

    def callback(event: Event):
        with lock:
            received.append(event)

    bus.subscribe(EventType.VOICE_COMMAND, callback)
    bus.start()

    # 多執行緒同時發布（減少數量以加快測試）
    def publisher(n):
        for i in range(20):
            bus.publish(Event(EventType.VOICE_COMMAND, {'id': f"{n}-{i}"}))

    threads = [threading.Thread(target=publisher, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    time.sleep(0.3)  # 等待所有事件處理完成

    assert len(received) == 60, f"應收到 60 個事件，實際 {len(received)}"
    print("[PASS] 執行緒安全測試通過")

    bus.stop()
    EventBus.reset_instance()


def test_latency():
    """測試事件延遲"""
    EventBus.reset_instance()
    bus = EventBus()
    latencies = []

    def callback(event: Event):
        latency = time.time() - event.timestamp
        latencies.append(latency)

    bus.subscribe(EventType.VOICE_COMMAND, callback)
    bus.start()

    # 發送多個事件測量延遲（減少數量加快測試）
    for _ in range(50):
        bus.publish(Event(EventType.VOICE_COMMAND, {}))
        time.sleep(0.001)

    time.sleep(0.15)

    avg_latency = sum(latencies) / len(latencies) * 1000  # ms
    max_latency = max(latencies) * 1000  # ms

    print(f"[INFO] 平均延遲: {avg_latency:.3f} ms")
    print(f"[INFO] 最大延遲: {max_latency:.3f} ms")

    assert avg_latency < 10, f"平均延遲應 <10ms，實際 {avg_latency:.3f}ms"
    print("[PASS] 延遲測試通過")

    bus.stop()
    EventBus.reset_instance()

    return avg_latency, max_latency


def test_unsubscribe():
    """測試取消訂閱"""
    EventBus.reset_instance()
    bus = EventBus()
    received = []

    def callback(event: Event):
        received.append(event)

    bus.subscribe(EventType.VOICE_COMMAND, callback)
    bus.start()

    bus.publish(Event(EventType.VOICE_COMMAND, {}))
    time.sleep(0.1)
    assert len(received) == 1

    # 取消訂閱
    bus.unsubscribe(EventType.VOICE_COMMAND, callback)
    bus.publish(Event(EventType.VOICE_COMMAND, {}))
    time.sleep(0.1)

    assert len(received) == 1, "取消訂閱後不應再收到事件"
    print("[PASS] 取消訂閱測試通過")

    bus.stop()
    EventBus.reset_instance()


def run_all_tests():
    """執行所有測試"""
    print("=" * 50)
    print("EventBus 單元測試")
    print("=" * 50)

    test_singleton()
    test_pubsub()
    test_multiple_subscribers()
    test_event_filtering()
    test_unsubscribe()
    test_thread_safety()
    avg_lat, max_lat = test_latency()

    print("=" * 50)
    print("所有測試通過!")
    print(f"延遲數據: avg={avg_lat:.3f}ms, max={max_lat:.3f}ms")
    print("=" * 50)

    return {
        'avg_latency_ms': avg_lat,
        'max_latency_ms': max_lat
    }


if __name__ == "__main__":
    run_all_tests()
