"""
EventBus - 執行緒安全的事件匯流排
用於 ECG、語音、遊戲模組間的通訊
"""

import queue
import threading
import time
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional


class EventType(Enum):
    """事件類型定義"""
    # ECG 事件
    ECG_PEAK = "ecg_peak"           # R-wave 偵測到
    ECG_BPM_UPDATE = "ecg_bpm"      # BPM 更新
    ECG_ERROR = "ecg_error"         # ECG 錯誤

    # 語音事件
    VOICE_COMMAND = "voice_command" # 語音指令辨識
    VOICE_NOISE = "voice_noise"     # 偵測到噪音
    VOICE_ERROR = "voice_error"     # 語音錯誤

    # 遊戲事件
    GAME_START = "game_start"
    GAME_PAUSE = "game_pause"
    GAME_OVER = "game_over"

    # 系統事件
    SYSTEM_SHUTDOWN = "shutdown"


@dataclass
class Event:
    """事件資料結構"""
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class EventBus:
    """
    執行緒安全的事件匯流排（Singleton）

    使用方式:
        bus = EventBus()
        bus.subscribe(EventType.VOICE_COMMAND, callback)
        bus.start()
        bus.publish(Event(EventType.VOICE_COMMAND, {'action': 'JUMP'}))
    """

    _instance: Optional['EventBus'] = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._subscribers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._queue: queue.Queue = queue.Queue()
        self._running = False
        self._dispatch_thread: Optional[threading.Thread] = None
        self._initialized = True

    def subscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """訂閱事件類型"""
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: EventType, callback: Callable[[Event], None]) -> None:
        """取消訂閱"""
        with self._lock:
            if event_type in self._subscribers:
                try:
                    self._subscribers[event_type].remove(callback)
                except ValueError:
                    pass

    def publish(self, event: Event) -> None:
        """發布事件（非阻塞）"""
        self._queue.put(event)

    def start(self) -> None:
        """啟動事件分發執行緒"""
        if self._running:
            return

        self._running = True
        self._dispatch_thread = threading.Thread(
            target=self._dispatch_loop,
            name="EventBus-Dispatcher",
            daemon=True
        )
        self._dispatch_thread.start()

    def stop(self) -> None:
        """停止事件匯流排"""
        if not self._running:
            return

        self._running = False
        # 發送關閉事件以喚醒分發執行緒
        self._queue.put(Event(EventType.SYSTEM_SHUTDOWN))

        if self._dispatch_thread:
            self._dispatch_thread.join(timeout=2.0)
            self._dispatch_thread = None

    def _dispatch_loop(self) -> None:
        """事件分發主迴圈"""
        while self._running:
            try:
                event = self._queue.get(timeout=0.1)

                if event.type == EventType.SYSTEM_SHUTDOWN:
                    # 通知所有關閉訂閱者
                    self._dispatch(event)
                    break

                self._dispatch(event)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"[EventBus] Dispatch error: {e}")

    def _dispatch(self, event: Event) -> None:
        """分發事件給訂閱者"""
        with self._lock:
            callbacks = self._subscribers.get(event.type, []).copy()

        for callback in callbacks:
            try:
                callback(event)
            except Exception as e:
                print(f"[EventBus] Callback error for {event.type}: {e}")

    def clear(self) -> None:
        """清除所有訂閱（用於測試）"""
        with self._lock:
            self._subscribers.clear()

        # 清空佇列
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    @classmethod
    def reset_instance(cls) -> None:
        """重置 Singleton（用於測試）"""
        with cls._lock:
            if cls._instance is not None:
                cls._instance.stop()
                cls._instance.clear()
            cls._instance = None

    @property
    def is_running(self) -> bool:
        """檢查是否正在運行"""
        return self._running

    @property
    def queue_size(self) -> int:
        """取得佇列大小"""
        return self._queue.qsize()
