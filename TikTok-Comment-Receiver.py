# ==============================================================================
# TIKTOK COMMENT RECEIVER (NATIVE PYQT6 - STABLE VERSION)
# Target: @isaackogz
# Logic: Uses Remote Sign Server + Native PyQt6 GUI
# ==============================================================================

import asyncio
import base64
import enum
import inspect
import json
import logging
import os
import random
import re
import sys
import traceback
import urllib.parse
import warnings
from abc import ABC, abstractmethod
from asyncio import AbstractEventLoop, Task, CancelledError
from dataclasses import dataclass, field
from functools import cached_property
from gzip import GzipFile
from http.cookies import SimpleCookie
from io import BytesIO
from json import JSONDecodeError
from logging import Logger
from typing import Optional, Type, Dict, Any, Union, Callable, List, Coroutine, AsyncIterator, Tuple, TypedDict, cast, Awaitable

# --- 3RD PARTY IMPORTS ---
import betterproto
import httpx
from httpx import Cookies, AsyncClient, Proxy, URL, Response
from pyee.asyncio import AsyncIOEventEmitter
from pyee.base import Handler
from python_socks import ProxyType, parse_proxy_url
from typing_extensions import deprecated

# --- PYQT6 IMPORTS (NATIVE ONLY) ---
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QObject
from PyQt6.QtWidgets import (QApplication, QVBoxLayout, QHBoxLayout, QWidget, 
                             QMainWindow, QPushButton, QLineEdit, QTextEdit, 
                             QLabel, QFrame)
from PyQt6.QtGui import QFont, QTextCursor, QColor

# --- WARNING FIX ---
warnings.filterwarnings("ignore", category=DeprecationWarning, module="websockets")
try:
    from websockets.exceptions import InvalidStatusCode
except ImportError:
    from websockets import InvalidStatusCode

from websockets.legacy.client import Connect, WebSocketClientProtocol
from websockets_proxy import websockets_proxy
from websockets_proxy.websockets_proxy import ProxyConnect

# ==============================================================================
# [BAGIAN 1-7: LOGIKA KONEKSI TIKTOK]
# (Bagian ini sama persis dengan logika core sebelumnya, tidak diubah)
# ==============================================================================

PACKAGE_VERSION = "6.0.0"

# Presets
Location = {"country": "ID", "city": "Jakarta", "lang": "id-ID", "lang_country": "id-ID", "tz_name": "Asia/Jakarta"}
Device = {
    "brand": "Microsoft", "model": "Windows PC", "os": "windows", "os_version": "10",
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "browser_name": "Mozilla", "browser_version": "5.0", "browser_platform": "Win32"
}
Screen = {"screen_width": 1920, "screen_height": 1080}
Last_RTT = str(random.randint(100, 200))

DEFAULT_WEB_CLIENT_PARAMS: Dict[str, Union[int, str]] = {
    "aid": 1988, "app_language": Location["lang"], "app_name": 'tiktok_web',
    "browser_language": Location["lang_country"], "browser_name": Device["browser_name"],
    "browser_online": "true", "browser_platform": Device["browser_platform"],
    "browser_version": Device["browser_version"], "cookie_enabled": "true",
    "device_platform": "web_pc", "focus_state": "true", "from_page": '',
    "history_len": random.randint(4, 14), "is_fullscreen": "false", "is_page_visible": "true",
    "screen_height": Screen["screen_height"], "screen_width": Screen["screen_width"],
    "tz_name": Location["tz_name"], "channel": "tiktok_web", "data_collection_enabled": "true",
    "os": Device["os"], "priority_region": Location["country"], "region": Location["country"],
    "user_is_login": "false", "webcast_language": Location["lang"], "msToken": "",
}

DEFAULT_WS_CLIENT_PARAMS: Dict[str, Union[int, str]] = {
    "aid": 1988, "app_language": Location["lang"], "app_name": "tiktok_web",
    "browser_platform": Device["browser_platform"], "browser_language": Location["lang_country"],
    "browser_name": Device["browser_name"], "browser_version": Device["browser_version"],
    "browser_online": "true", "cookie_enabled": "true", "tz_name": Location["tz_name"],
    "device_platform": "web", "debug": "false", "host": urllib.parse.quote_plus("https://webcast.tiktok.com"),
    "identity": "audience", "live_id": "12", "sup_ws_ds_opt": "1", "update_version_code": "2.0.0",
    "version_code": "180800", "did_rule": "3", "screen_height": Screen["screen_height"],
    "screen_width": Screen["screen_width"], "heartbeat_duration": "0", "resp_content_type": "protobuf",
    "history_comment_count": "6", "last_rtt": Last_RTT
}

DEFAULT_WS_CLIENT_PARAMS_APPEND_STR: str = "&version_code=270000"
DEFAULT_REQUEST_HEADERS: Dict[str, str] = {
    "Connection": 'keep-alive', 'Cache-Control': 'max-age=0', 'User-Agent': Device["user_agent"],
    "Accept": 'text/html,application/json,application/protobuf', "Referer": 'https://www.tiktok.com/',
    "Origin": 'https://www.tiktok.com', 'Accept-Language': 'en-US,en;q=0.9',
    'Accept-Encoding': 'gzip, deflate', "Sec-Fetch-Site": 'same-site', "Sec-Fetch-Mode": 'cors',
    "Sec-Fetch-Dest": 'empty', "Sec-Fetch-Ua-Mobile": '?0',
}
DEFAULT_COOKIES: Dict[str, str] = {"tt-target-idc": "useast1a"}
CLIENT_NAME: str = "ttlive-python"

@dataclass()
class _WebDefaults:
    tiktok_app_url: str = "https://www.tiktok.com"
    tiktok_sign_url: str = "https://tiktok.eulerstream.com"
    tiktok_webcast_url: str = 'https://webcast.tiktok.com/webcast'
    web_client_params: dict = field(default_factory=lambda: DEFAULT_WEB_CLIENT_PARAMS)
    web_client_headers: dict = field(default_factory=lambda: DEFAULT_REQUEST_HEADERS)
    web_client_cookies: dict = field(default_factory=lambda: DEFAULT_COOKIES)
    ws_client_params: dict = field(default_factory=lambda: DEFAULT_WS_CLIENT_PARAMS)
    ws_client_params_append_str: str = field(default_factory=lambda: DEFAULT_WS_CLIENT_PARAMS_APPEND_STR)
    tiktok_sign_api_key: Optional[str] = None
    ja3_impersonate: str = "chrome131"

WebDefaults: _WebDefaults = _WebDefaults()

# ==============================================================================
# SECTION 2: LOGGING (SIMPLIFIED & STABLE)
# ==============================================================================

class LogLevel(enum.Enum):
    CRITICAL = 50; ERROR = 40; WARNING = 30; INFO = 20; DEBUG = 10; NOTSET = 0
    @property
    def value(self) -> int: return cast(int, super().value)

class TikTokLiveLogHandler(logging.StreamHandler):
    LOGGER_NAME: str = "TikTokLive"
    LOGGER: Optional[logging.Logger] = None
    TIME_FORMAT: str = "%H:%M:%S"
    
    # Hapus 'stack' dari format string agar tidak error KeyError
    FORMAT: str = "[%(name)s] %(levelname)s — %(message)s"

    def __init__(self, stream: Optional[Any] = None, formatter: Optional[logging.Formatter] = None):
        super().__init__(stream=stream or sys.stderr)
        self.formatter = formatter or logging.Formatter(self.FORMAT, self.TIME_FORMAT)

    @classmethod
    def get_logger(cls, level: Optional[LogLevel] = None, stream: Optional[Any] = None) -> logging.Logger:
        if cls.LOGGER and not level: return cls.LOGGER
        if not cls.LOGGER:
            log_handler: TikTokLiveLogHandler = TikTokLiveLogHandler(stream)
            cls.LOGGER = logging.getLogger(cls.LOGGER_NAME)
            cls.LOGGER.addHandler(log_handler)
            # Cegah log ganda (propagate false)
            cls.LOGGER.propagate = False
        
        cls.LOGGER.setLevel((level if level is not None else LogLevel.WARNING).value)
        return cls.LOGGER

    def emit(self, record: logging.LogRecord) -> None:
        # Implementasi emit standar yang aman
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

# --- ERRORS ---
class TikTokLiveError(RuntimeError):
    def __init__(self, *args):
        args = list(args)
        args.insert(0, f"TikTokLive v{PACKAGE_VERSION} ->")
        if len(args) == 1: args.append(self.__class__.__name__)
        super().__init__(" ".join(args))

class AlreadyConnectedError(TikTokLiveError): pass
class UserOfflineError(TikTokLiveError): pass
class UserNotFoundError(TikTokLiveError):
    def __init__(self, unique_id: str, *args):
        self.unique_id: str = unique_id
        super().__init__(*args)
class AgeRestrictedError(TikTokLiveError): pass
class InitialCursorMissingError(TikTokLiveError): pass
class WebsocketURLMissingError(TikTokLiveError): pass
class WebcastBlocked200Error(TikTokLiveError): pass
class SignAPIError(TikTokLiveError):
    class ErrorReason(enum.Enum):
        RATE_LIMIT = 1; CONNECT_ERROR = 2; EMPTY_PAYLOAD = 3; SIGN_NOT_200 = 4
        EMPTY_COOKIES = 5; PREMIUM_ENDPOINT = 6; AUTHENTICATED_WS = 7
    def __init__(self, reason: ErrorReason, *args: str, response: Optional[httpx.Response] = None):
        self._response = response
        self.reason = reason
        args = list(args)
        args.insert(0, f"[{reason.name}]")
        super().__init__(" ".join(args))
    @property
    def response(self) -> httpx.Response | None: return self._response
class SignatureRateLimitError(SignAPIError):
    def __init__(self, api_message: Optional[str], *args, response: httpx.Response):
        super().__init__(SignAPIError.ErrorReason.RATE_LIMIT, *args, response=response)
class AuthenticatedWebSocketConnectionError(SignAPIError):
    def __init__(self, *args, **kwargs):
        super().__init__(SignAPIError.ErrorReason.AUTHENTICATED_WS, *args, **kwargs)
class FailedParseAppInfo(TikTokLiveError): pass
class FailedResolveUserId(TikTokLiveError): pass
class FailedParseRoomIdError(TikTokLiveError): pass

# --- PROTOCOLS ---
class WebcastWSAckPayload(TypedDict):
    server_fetch_time: int
    push_time: int
    msg_type: str
    seq_id: int
    is_from_ws_proxy: bool

@dataclass(eq=False, repr=False)
class WebcastPushFrame(betterproto.Message):
    seq_id: int = betterproto.uint64_field(1)
    log_id: int = betterproto.uint64_field(2)
    service: int = betterproto.uint64_field(3)
    method: int = betterproto.uint64_field(4)
    headers: Dict[str, str] = betterproto.map_field(5, betterproto.TYPE_STRING, betterproto.TYPE_STRING)
    payload_encoding: str = betterproto.string_field(6)
    payload_type: str = betterproto.string_field(7)
    payload: bytes = betterproto.bytes_field(8)

@dataclass(eq=False, repr=False)
class HeartbeatMessage(betterproto.Message):
    room_id: int = betterproto.uint64_field(1)
    send_packet_seq_id: int = betterproto.uint64_field(2)

@dataclass(eq=False, repr=False)
class WebcastImEnterRoomMessage(betterproto.Message):
    room_id: int = betterproto.int64_field(1)
    room_tag: str = betterproto.string_field(2)
    live_region: str = betterproto.string_field(3)
    live_id: int = betterproto.int64_field(4)
    identity: str = betterproto.string_field(5)
    cursor: str = betterproto.string_field(6)
    account_type: int = betterproto.int64_field(7)
    enter_unique_id: int = betterproto.int64_field(8)
    filter_welcome_msg: str = betterproto.string_field(9)
    is_anchor_continue_keep_msg: bool = betterproto.bool_field(10)

class ControlAction(betterproto.Enum):
    CONTROL_ACTION_UNKNOWN = 0; CONTROL_ACTION_STREAM_PAUSED = 1; CONTROL_ACTION_STREAM_UNPAUSED = 2
    CONTROL_ACTION_STREAM_ENDED = 3; CONTROL_ACTION_STREAM_SUSPENDED = 4

@dataclass(eq=False, repr=False)
class CommonMessageData(betterproto.Message):
    method: str = betterproto.string_field(1)
    message_id: int = betterproto.int64_field(2)
    room_id: int = betterproto.int64_field(3)
    create_time: int = betterproto.int64_field(4)
    monitor: int = betterproto.int32_field(5)
    show_msg: bool = betterproto.bool_field(6)
    describe: str = betterproto.string_field(7)
    display_text: "Text" = betterproto.message_field(8)
    fold_type: int = betterproto.int64_field(9)
    anchor_fold_type: int = betterproto.int64_field(10)
    priority_score: int = betterproto.int64_field(11)
    log_id: str = betterproto.string_field(12)
    msg_process_filter_k: str = betterproto.string_field(13)
    msg_process_filter_v: str = betterproto.string_field(14)
    from_idc: str = betterproto.string_field(15)
    to_idc: str = betterproto.string_field(16)
    filter_tags: List[str] = betterproto.string_field(17)
    client_send_time: int = betterproto.int64_field(25)

@dataclass(eq=False, repr=False)
class ImageModel(betterproto.Message):
    m_urls: List[str] = betterproto.string_field(1)
    m_uri: str = betterproto.string_field(2)
    height: int = betterproto.int32_field(3)
    width: int = betterproto.int32_field(4)
    avg_color: str = betterproto.string_field(5)
    image_type: int = betterproto.int32_field(6)
    schema: str = betterproto.string_field(7)
    is_animated: bool = betterproto.bool_field(9)

@dataclass(eq=False, repr=False)
class User(betterproto.Message):
    id: int = betterproto.int64_field(1)
    nick_name: str = betterproto.string_field(3)
    avatar_thumb: "ImageModel" = betterproto.message_field(9)
    avatar_medium: "ImageModel" = betterproto.message_field(10)
    avatar_large: "ImageModel" = betterproto.message_field(11)
    is_verified: bool = betterproto.bool_field(12)
    status: int = betterproto.int32_field(15)
    create_time: int = betterproto.int64_field(16)
    modify_time: int = betterproto.int64_field(17)
    secret: int = betterproto.int32_field(18)
    share_qrcode_uri: str = betterproto.string_field(19)
    special_id: str = betterproto.string_field(26)
    top_vip_no: int = betterproto.int32_field(31)
    pay_score: int = betterproto.int64_field(34)
    fan_ticket_count: int = betterproto.int64_field(35)
    username: str = betterproto.string_field(38)
    sec_uid: str = betterproto.string_field(46)
    display_id: str = betterproto.string_field(12)

@dataclass(eq=False, repr=False)
class TextFormat(betterproto.Message):
    color: str = betterproto.string_field(1)
    bold: bool = betterproto.bool_field(2)
    italic: bool = betterproto.bool_field(3)
    weight: int = betterproto.int32_field(4)
    italic_angle: int = betterproto.int32_field(5)
    font_size: int = betterproto.int32_field(6)
    use_heigh_light_color: bool = betterproto.bool_field(7)
    use_remote_color: bool = betterproto.bool_field(8)

@dataclass(eq=False, repr=False)
class TextPiece(betterproto.Message):
    type: int = betterproto.int32_field(1)
    format: "TextFormat" = betterproto.message_field(2)
    string_value: str = betterproto.string_field(11)

@dataclass(eq=False, repr=False)
class Text(betterproto.Message):
    key: str = betterproto.string_field(1)
    default_pattern: str = betterproto.string_field(2)
    default_format: "TextFormat" = betterproto.message_field(3)
    pieces: List["TextPiece"] = betterproto.message_field(4)

@dataclass(eq=False, repr=False)
class WebcastChatMessage(betterproto.Message):
    base_message: "CommonMessageData" = betterproto.message_field(1)
    user_info: "User" = betterproto.message_field(2)
    content: str = betterproto.string_field(3)
    visible_to_sender: bool = betterproto.bool_field(4)
    background_image_v2: "ImageModel" = betterproto.message_field(7)
    at_user: "User" = betterproto.message_field(12)
    content_language: str = betterproto.string_field(14)

@dataclass(eq=False, repr=False)
class WebcastMemberMessage(betterproto.Message):
    base_message: "CommonMessageData" = betterproto.message_field(1)
    user: "User" = betterproto.message_field(2)
    count: int = betterproto.int32_field(3)
    operator: "User" = betterproto.message_field(4)
    action: int = betterproto.int32_field(10)

@dataclass(eq=False, repr=False)
class ProtoMessageFetchResult(betterproto.Message):
    messages: List["ProtoMessageFetchResultBaseProtoMessage"] = (betterproto.message_field(1))
    cursor: str = betterproto.string_field(2)
    fetch_interval: int = betterproto.int64_field(3)
    now: int = betterproto.int64_field(4)
    internal_ext: str = betterproto.string_field(5)
    fetch_type: int = betterproto.int32_field(6)
    route_params: Dict[str, str] = betterproto.map_field(7, betterproto.TYPE_STRING, betterproto.TYPE_STRING)
    heartbeat_duration: int = betterproto.int64_field(8)
    need_ack: bool = betterproto.bool_field(9)
    push_server: str = betterproto.string_field(10)
    is_first: bool = betterproto.bool_field(11)

@dataclass(eq=False, repr=False)
class ProtoMessageFetchResultBaseProtoMessage(betterproto.Message):
    method: str = betterproto.string_field(1)
    payload: bytes = betterproto.bytes_field(2)
    msg_id: int = betterproto.int64_field(3)
    msg_type: int = betterproto.int32_field(4)
    offset: int = betterproto.int64_field(5)

@dataclass(eq=False, repr=False)
class WebcastControlMessage(betterproto.Message):
    base_message: "CommonMessageData" = betterproto.message_field(1)
    action: int = betterproto.int32_field(2)

# --- EVENTS ---
class BaseEvent:
    @property
    def type(self) -> str: return self.get_type()
    @classmethod
    def get_type(cls) -> str: return cls.__name__
    @property
    def bytes(self) -> Optional[bytes]: return self.payload if hasattr(self, 'payload') else None
    @property
    def as_base64(self) -> str: return base64.b64encode(self.bytes).decode()
    @property
    def size(self) -> int: return len(self.bytes) if self.bytes else -1

class ExtendedUser(User):
    @classmethod
    def from_user(cls, user: User): return user

class CommentEvent(BaseEvent, WebcastChatMessage):
    user_info: ExtendedUser
    at_user: ExtendedUser
    @property
    def user(self) -> ExtendedUser: return ExtendedUser.from_user(self.user_info)
    @property
    def comment(self) -> str: return self.content

class ControlEvent(BaseEvent, WebcastControlMessage):
    action: ControlAction = betterproto.enum_field(2)

class WebsocketResponseEvent(ProtoMessageFetchResult, BaseEvent): pass
class UnknownEvent(WebsocketResponseEvent): pass

@dataclass()
class ConnectEvent(BaseEvent):
    unique_id: str
    room_id: int

class DisconnectEvent(BaseEvent): pass
class LiveEndEvent(ControlEvent): pass
class LivePauseEvent(ControlEvent): pass
class LiveUnpauseEvent(ControlEvent): pass

EVENT_MAPPINGS: Dict[str, BaseEvent] = {"WebcastChatMessage": CommentEvent, "WebcastControlMessage": ControlEvent}
ProtoEvent = Union[CommentEvent, ControlEvent]
CustomEvent = Union[WebsocketResponseEvent, UnknownEvent, ConnectEvent, LiveEndEvent, LivePauseEvent, LiveUnpauseEvent, DisconnectEvent]

# --- CLIENT LOGIC ---
def build_webcast_uri(initial_webcast_response: ProtoMessageFetchResult, base_uri_params: dict, base_uri_append_str: str) -> str:
    if not initial_webcast_response.cursor: raise InitialCursorMissingError("Missing cursor.")
    if not initial_webcast_response.push_server: raise WebsocketURLMissingError("No websocket URL.")
    uri_params: dict = {
        **initial_webcast_response.route_params, **base_uri_params,
        "internal_ext": initial_webcast_response.internal_ext, "cursor": initial_webcast_response.cursor,
    }
    return (initial_webcast_response.push_server + "?" + '&'.join(f"{key}={value}" for key, value in uri_params.items()) + base_uri_append_str)

def extract_webcast_response_message(push_frame: WebcastPushFrame, logger: logging.Logger = TikTokLiveLogHandler.get_logger()) -> ProtoMessageFetchResult:
    if not push_frame.headers or 'compress_type' not in push_frame.headers or push_frame.headers['compress_type'] == 'none':
        return ProtoMessageFetchResult().parse(push_frame.payload)
    if push_frame.headers.get('compress_type', None) != 'gzip':
        return ProtoMessageFetchResult().parse(push_frame.payload)
    gzip_file = GzipFile(fileobj=BytesIO(push_frame.payload))
    try: decompressed_bytes = gzip_file.read()
    finally: gzip_file.close()
    return ProtoMessageFetchResult().parse(decompressed_bytes)

def extract_websocket_options(headers: dict) -> dict[str, str]:
    options = SimpleCookie()
    options.load(headers.get('Handshake-Options', ''))
    return {key: value.value for key, value in options.items()}

def check_authenticated_session(session_id: Optional[str], tt_target_idc: Optional[str], session_required: bool) -> bool:
    if not session_id:
        if session_required: raise ValueError("Session ID required.")
        return False
    if not tt_target_idc: raise ValueError("Target IDC required.")
    return True

class TikTokSigner:
    def __init__(self, *args, **kwargs):
        self.client = httpx.AsyncClient()

WebcastProxy = Union[httpx.Proxy, websockets_proxy.Proxy]
WebcastIterator = AsyncIterator[Tuple[Optional[WebcastPushFrame], ProtoMessageFetchResult]]

class WebcastConnect(Connect):
    def __init__(self, initial_webcast_response: ProtoMessageFetchResult, logger: logging.Logger, base_uri_params: Dict[str, Any], base_uri_append_str: str, uri: Optional[str] = None, **kwargs):
        if uri is None: uri = build_webcast_uri(initial_webcast_response, base_uri_params, base_uri_append_str)
        super().__init__(uri, logger=logger, **kwargs)
        self.logger = self._logger = logger
        self._ws: Optional[WebSocketClientProtocol] = None
        self._ws_options: Optional[dict[str, str]] = None
        self._initial_response: ProtoMessageFetchResult = initial_webcast_response
    @property
    def ws(self) -> Optional[WebSocketClientProtocol]: return self._ws
    @property
    def ws_options(self) -> Optional[dict[str, str]]: return self._ws_options
    async def __aiter__(self) -> WebcastIterator:
        try:
            async with self as protocol:
                self._ws = protocol
                self._ws_options = extract_websocket_options(self._ws.response_headers)
                yield None, self._initial_response
                async for payload_bytes in protocol:
                    webcast_push_frame: WebcastPushFrame = WebcastPushFrame().parse(payload_bytes)
                    if webcast_push_frame.payload_type != "msg": continue
                    webcast_response: ProtoMessageFetchResult = extract_webcast_response_message(webcast_push_frame, logger=self._logger)
                    yield webcast_push_frame, webcast_response
        except InvalidStatusCode as ex:
            if ex.status_code == 200: raise WebcastBlocked200Error(f"WebSocket rejected: {ex.headers.get('Handshake-Msg')}") from ex
            raise
        finally: self._ws = None; self._ws_options = None

class WebcastProxyConnect(WebcastConnect, ProxyConnect):
    def __init__(self, proxy: Optional[WebcastProxy], **kwargs):
        super().__init__(proxy=self._convert_proxy(proxy) if isinstance(proxy, httpx.Proxy) else proxy, **kwargs)
    @classmethod
    def _convert_proxy(cls, proxy: httpx.Proxy) -> websockets_proxy.Proxy:
        parsed = list(parse_proxy_url(str(proxy.url)))
        parsed[3], parsed[4] = proxy.auth[0], proxy.auth[1]
        return websockets_proxy.Proxy(*parsed)

class WebcastWSClient:
    DEFAULT_PING_INTERVAL: float = 5.0
    def __init__(self, ws_kwargs: Optional[dict] = None, ws_proxy: Optional[WebcastProxy] = None):
        self._seq_id: int = 1
        self._ws_kwargs: dict = ws_kwargs or {}
        self._logger = TikTokLiveLogHandler.get_logger()
        self._ping_loop: Optional[Task] = None
        self._ws_proxy: Optional[WebcastProxy] = ws_proxy or ws_kwargs.get("proxy")
        self._connect_generator_class = WebcastProxyConnect if self._ws_proxy else WebcastConnect
        self._connection_generator: Optional[WebcastConnect] = None
    @property
    def ws(self) -> Optional[WebSocketClientProtocol]: return self._connection_generator.ws if self._connection_generator else None
    @property
    def connected(self) -> bool: return self.ws and self.ws.open
    async def send(self, message: Union[bytes, betterproto.Message]) -> None:
        if not self.connected: return
        await self.ws.send(message=bytes(message) if isinstance(message, betterproto.Message) else message)
    async def send_ack(self, webcast_response: ProtoMessageFetchResult, webcast_push_frame: WebcastPushFrame) -> None:
        if not self.connected: return
        await self.send(message=WebcastPushFrame(payload_type="ack", payload_encoding="pb", log_id=webcast_push_frame.log_id, payload=(webcast_response.internal_ext or "-").encode()))
    async def disconnect(self) -> None:
        if not self.connected: return
        await self.ws.close()
    def get_ws_cookie_string(self, cookies: httpx.Cookies) -> str:
        return " ".join([f"{key}={value};" for key, value in cookies.items()])
    async def connect(self, room_id: int, cookies: httpx.Cookies, user_agent: str, initial_webcast_response: ProtoMessageFetchResult, process_connect_events: bool = True, compress_ws_events: bool = True) -> AsyncIterator[ProtoMessageFetchResult]:
        ws_kwargs: dict = self._ws_kwargs.copy()
        if self._ws_proxy is not None:
            ws_kwargs["proxy_conn_timeout"] = ws_kwargs.get("proxy_conn_timeout", 10.0)
            ws_kwargs["proxy"] = self._ws_proxy
        if not process_connect_events: initial_webcast_response.messages = []
        self._connection_generator = self._connect_generator_class(
            initial_webcast_response=initial_webcast_response,
            subprotocols=ws_kwargs.pop("subprotocols", ["echo-protocol"]),
            logger=self._logger,
            base_uri_append_str=WebDefaults.ws_client_params_append_str,
            base_uri_params={**WebDefaults.ws_client_params, "room_id": room_id, "compress": "gzip" if compress_ws_events else ""},
            extra_headers={"Cookie": self.get_ws_cookie_string(cookies), "User-Agent": user_agent, **ws_kwargs.pop("extra_headers", {})},
            **{**ws_kwargs, "ping_timeout": None, "ping_interval": None}
        )
        async for webcast_push_frame, webcast_response in cast(WebcastIterator, self._connection_generator):
            if webcast_response.is_first: await self.switch_rooms(room_id=room_id)
            if webcast_response.need_ack: await self.send_ack(webcast_response=webcast_response, webcast_push_frame=webcast_push_frame)
            yield webcast_response
            if not self.connected: break
        if self._ping_loop and not self._ping_loop.done():
            self._ping_loop.cancel()
            await self._ping_loop
        self._ping_loop = None
        self._connection_generator = None
    def restart_ping_loop(self, room_id: int) -> None:
        if self._ping_loop: self._ping_loop.cancel()
        self._seq_id = 1
        self._ping_loop = asyncio.create_task(self._ping_loop_fn(room_id))
    async def switch_rooms(self, room_id: int) -> None:
        im_enter_room_message = WebcastImEnterRoomMessage(room_id=room_id, live_id=12, identity="audience", filter_welcome_msg="0", is_anchor_continue_keep_msg=False)
        webcast_push_frame = WebcastPushFrame(payload_type="im_enter_room", payload_encoding="pb", payload=bytes(im_enter_room_message))
        await self.send(message=webcast_push_frame)
        self.restart_ping_loop(room_id=room_id)
    async def _ping_loop_fn(self, room_id: int) -> None:
        try:
            if not self.connected: return
            ping_interval = WebcastWSClient.DEFAULT_PING_INTERVAL
            if self._connection_generator and self._connection_generator.ws_options:
                ping_interval = float(self._connection_generator.ws_options.get("ping-interval", ping_interval))
            while self.connected:
                hb_message = HeartbeatMessage(room_id=room_id, send_packet_seq_id=self._seq_id)
                self._seq_id += 1
                webcast_push_frame = WebcastPushFrame(payload_encoding="pb", payload_type="hb", payload=bytes(hb_message), headers={})
                await self.send(message=webcast_push_frame)
                await asyncio.sleep(ping_interval)
        except asyncio.CancelledError: pass
        except Exception: self._logger.error("Ping loop failed", exc_info=True)

class TikTokHTTPClient:
    def __init__(self, web_proxy: Optional[Proxy] = None, httpx_kwargs: Optional[dict] = None):
        self.cookies = Cookies(WebDefaults.web_client_cookies)
        self.headers = WebDefaults.web_client_headers
        self.params = WebDefaults.web_client_params
        self._httpx = AsyncClient(proxy=web_proxy, cookies=self.cookies, **(httpx_kwargs or {}))
        self._tiktok_signer = TikTokSigner()
    @property
    def signer(self) -> TikTokSigner: return self._tiktok_signer
    async def close(self) -> None: await self._httpx.aclose()
    async def get(self, url: str, extra_params: dict = None, **kwargs) -> Response:
        return await self._httpx.get(url, params={**self.params, **(extra_params or {})}, headers=self.headers, cookies=self.cookies)

class ClientRoute(ABC):
    def __init__(self, web: TikTokHTTPClient):
        self._web = web
        self._logger = TikTokLiveLogHandler.get_logger()
    @abstractmethod
    def __call__(self, **kwargs: Any) -> Awaitable[Any]: raise NotImplementedError

class FetchRoomIdLiveHTMLRoute(ClientRoute):
    SIGI_PATTERN: re.Pattern = re.compile(r"""<script id="SIGI_STATE" type="application/json">(.*?)</script>""")
    async def __call__(self, unique_id: str) -> str:
        response: Response = await self._web.get(url=WebDefaults.tiktok_app_url + f"/@{unique_id}/live")
        match = self.SIGI_PATTERN.search(response.text)
        if match is None: raise FailedParseRoomIdError("Failed to extract SIGI_STATE.")
        try: sigi_state = json.loads(match.group(1))
        except JSONDecodeError: raise FailedParseRoomIdError("Failed to parse SIGI_STATE.")
        if sigi_state.get('LiveRoom') is None: raise UserNotFoundError("User not LIVE or invalid.")
        room_data = sigi_state["LiveRoom"]["liveRoomUserInfo"]["user"]
        if room_data.get('status') == 4: raise UserOfflineError("User is offline.")
        return room_data.get('roomId')

class WebcastPlatform(enum.Enum):
    WEB = "web"; MOBILE = "mobile"

class FetchSignedWebSocketRoute(ClientRoute):
    async def __call__(self, platform: WebcastPlatform, room_id: Optional[int] = None, session_id: Optional[str] = None, tt_target_idc: Optional[str] = None) -> ProtoMessageFetchResult:
        signer_client: httpx.AsyncClient = self._web.signer.client
        sign_params: dict = {
            'client': CLIENT_NAME,
            'room_id': room_id or self._web.params.get('room_id', None),
            'user_agent': self._web.headers['User-Agent'],
            'platform': platform.value,
            'client_enter': True
        }
        session_id = session_id or self._web.cookies.get('sessionid')
        tt_target_idc = tt_target_idc or self._web.cookies.get('tt-target-idc')
        if check_authenticated_session(session_id, tt_target_idc, session_required=False):
            sign_params['session_id'] = session_id
            sign_params['tt_target_idc'] = tt_target_idc
        try:
            response: httpx.Response = await signer_client.get(url=WebDefaults.tiktok_sign_url + "/webcast/fetch/", params=sign_params, timeout=15)
        except httpx.ConnectError as ex:
            raise SignAPIError(SignAPIError.ErrorReason.CONNECT_ERROR, "Failed to connect to sign server!", response=None) from ex
        data: bytes = await response.aread()
        if response.status_code == 429: raise SignatureRateLimitError("Rate Limit", "Too many connections.", response=response)
        elif not data: raise SignAPIError(SignAPIError.ErrorReason.EMPTY_PAYLOAD, "Sign API empty.", response=response)
        elif response.status_code != 200: raise SignAPIError(SignAPIError.ErrorReason.SIGN_NOT_200, f"Sign API Error: {response.status_code}", response=response)
        self._update_client_cookies(response)
        return extract_webcast_response_message(logger=self._logger, push_frame=WebcastPushFrame(log_id=-1, payload=data, payload_type="msg"))
    def _update_client_cookies(self, response: Response) -> None:
        jar: SimpleCookie = SimpleCookie()
        cookies_header: Optional[str] = response.headers.get("X-Set-TT-Cookie")
        if not cookies_header: raise SignAPIError(SignAPIError.ErrorReason.EMPTY_COOKIES, "Sign server no cookies!", response=response)
        jar.load(cookies_header)
        for cookie, morsel in jar.items():
            if self._web.cookies.get(cookie): self._web.cookies.delete(cookie)
            self._web.cookies.set(cookie, morsel.value, ".tiktok.com")

class TikTokWebClient(TikTokHTTPClient):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.fetch_room_id_from_html = FetchRoomIdLiveHTMLRoute(self)
        self.fetch_signed_websocket = FetchSignedWebSocketRoute(self)

class TikTokLiveClient(AsyncIOEventEmitter):
    def __init__(self, unique_id: str | int, platform: WebcastPlatform = WebcastPlatform.WEB, web_proxy: Optional[httpx.Proxy] = None, ws_proxy: Optional[WebcastProxy] = None, web_kwargs: Optional[dict] = None, ws_kwargs: Optional[dict] = None):
        super().__init__()
        self._ws: WebcastWSClient = WebcastWSClient(ws_kwargs=ws_kwargs or {}, ws_proxy=ws_proxy)
        self._web: TikTokWebClient = TikTokWebClient(web_proxy=web_proxy or (web_kwargs or {}).pop("web_proxy", None), **(web_kwargs or {}))
        self._web.params['referer'] = f"https://www.tiktok.com/@{unique_id}/live"
        self._web.params['root_referer'] = f"https://www.tiktok.com/@{unique_id}/live"
        self._logger: Logger = TikTokLiveLogHandler.get_logger(level=LogLevel.INFO)
        self.ignore_broken_payload: bool = False
        self._ws_platform: WebcastPlatform = platform
        self._unique_id: str = self.parse_unique_id(unique_id)
        self._room_id: Optional[int] = None
        self._event_loop_task: Optional[Task] = None
    @classmethod
    def parse_unique_id(cls, unique_id: str) -> str:
        return unique_id.replace(WebDefaults.tiktok_app_url + "/", "").replace("/live", "").replace("@", "", 1).strip()
    async def start(self, process_connect_events: bool = True, compress_ws_events: bool = True, room_id: Optional[int] = None) -> Task:
        if self._ws.connected: raise AlreadyConnectedError("Already connected!")
        try: self._room_id = int(room_id or await self._web.fetch_room_id_from_html(self._unique_id))
        except Exception as e: self._logger.error(f"Failed to fetch room ID: {e}"); raise e
        self._web.params["room_id"] = str(self._room_id)
        self._logger.info(f"Connected to Room ID: {self._room_id}")
        initial_webcast_response: ProtoMessageFetchResult = await self._web.fetch_signed_websocket(self._ws_platform)
        self._event_loop_task = self._asyncio_loop.create_task(self._ws_client_loop(initial_webcast_response, process_connect_events, compress_ws_events))
        return self._event_loop_task
    async def connect(self, callback: Optional[Callable] = None, **kwargs) -> Task:
        task: Task = await self.start(**kwargs)
        try:
            if inspect.iscoroutinefunction(callback): self._asyncio_loop.create_task(callback())
            elif inspect.isfunction(callback): callback()
            await task
        except CancelledError: self._logger.debug("Client stopped.")
        return task
    def run(self, **kwargs) -> Task: return self._asyncio_loop.run_until_complete(self.connect(**kwargs))
    async def disconnect(self) -> None:
        await self._ws.disconnect()
        if self._event_loop_task:
            try: await self._event_loop_task
            except: pass
            self._event_loop_task = None
        await self._web.close()
    def on(self, event: Type[BaseEvent], f: Optional[Callable] = None): return super().on(event.get_type(), f)
    def add_listener(self, event: Type[BaseEvent], f: Callable): return super().add_listener(event=event if isinstance(event, str) else event.get_type(), f=f)
    async def _ws_client_loop(self, initial_webcast_response: ProtoMessageFetchResult, process_connect_events: bool, compress_ws_events: bool) -> None:
        async for webcast_response in self._ws.connect(initial_webcast_response=initial_webcast_response, process_connect_events=process_connect_events, compress_ws_events=compress_ws_events, cookies=self._web.cookies, room_id=self._room_id, user_agent=self._web.headers['User-Agent']):
            async for event in self._parse_webcast_response(webcast_response): self.emit(event.type, event)
        self.emit(DisconnectEvent.get_type(), DisconnectEvent())
    async def _parse_webcast_response(self, webcast_response: ProtoMessageFetchResult) -> AsyncIterator[BaseEvent]:
        if webcast_response.is_first: yield ConnectEvent(unique_id=self._unique_id, room_id=self._room_id)
        for message in webcast_response.messages:
            for event in await self._parse_webcast_response_message(message):
                if event: yield event
    async def _parse_webcast_response_message(self, webcast_response_message: Optional[ProtoMessageFetchResultBaseProtoMessage]) -> List[BaseEvent]:
        if not webcast_response_message: return []
        event_type: Optional[Type[BaseEvent]] = EVENT_MAPPINGS.get(webcast_response_message.method)
        response_event = WebsocketResponseEvent().from_dict(webcast_response_message.to_dict()) # type: ignore
        if event_type is None: return [response_event, UnknownEvent().from_dict(webcast_response_message.to_dict())] # type: ignore
        try: proto_event: BaseEvent = event_type().parse(webcast_response_message.payload) # type: ignore
        except Exception:
            if not self.ignore_broken_payload: self._logger.error(traceback.format_exc())
            return [response_event]
        parsed_events: List[BaseEvent] = [response_event, proto_event]
        if isinstance(proto_event, ControlEvent):
            if proto_event.action in {ControlAction.CONTROL_ACTION_STREAM_ENDED, ControlAction.CONTROL_ACTION_STREAM_SUSPENDED}:
                self._asyncio_loop.create_task(self.disconnect())
                return [*parsed_events, LiveEndEvent().parse(webcast_response_message.payload)] # type: ignore
            elif proto_event.action == ControlAction.CONTROL_ACTION_STREAM_PAUSED: return [*parsed_events, LivePauseEvent().parse(webcast_response_message.payload)] # type: ignore
            elif proto_event.action == ControlAction.CONTROL_ACTION_STREAM_UNPAUSED: return [*parsed_events, LiveUnpauseEvent().parse(webcast_response_message.payload)] # type: ignore
        return parsed_events
    @property
    def room_id(self) -> Optional[int]: return self._room_id
    @property
    def _asyncio_loop(self) -> AbstractEventLoop:
        try: return asyncio.get_running_loop()
        except RuntimeError: return asyncio.new_event_loop()

# ==============================================================================
# GUI SECTION (NATIVE PYQT6)
# ==============================================================================

class TikTokWorker(QThread):
    sig_connected = pyqtSignal(str, int)
    sig_disconnected = pyqtSignal()
    sig_comment = pyqtSignal(str, str)
    sig_error = pyqtSignal(str)
    sig_log = pyqtSignal(str)

    def __init__(self, unique_id):
        super().__init__()
        self.unique_id = unique_id
        self.client: Optional[TikTokLiveClient] = None
        self.loop: Optional[AbstractEventLoop] = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.client = TikTokLiveClient(unique_id=self.unique_id)

        @self.client.on(ConnectEvent)
        async def on_connect(event: ConnectEvent):
            self.sig_connected.emit(event.unique_id, event.room_id)
            self.sig_log.emit(f"System: Terhubung ke Room ID {event.room_id}")

        @self.client.on(DisconnectEvent)
        async def on_disconnect(event: DisconnectEvent):
            self.sig_log.emit("System: Terputus dari server.")

        @self.client.on(CommentEvent)
        async def on_comment(event: CommentEvent):
            self.sig_comment.emit(event.user.nick_name, event.comment)

        try:
            self.sig_log.emit(f"System: Menghubungi {self.unique_id}...")
            self.client.run()
        except Exception as e:
            if "Cancelled" not in str(e):
                self.sig_error.emit(str(e))
        finally:
            self.sig_disconnected.emit()

    def stop(self):
        if self.client and self.client.connected:
            asyncio.run_coroutine_threadsafe(self.client.disconnect(), self.loop)
        self.quit()
        self.wait()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.worker: Optional[TikTokWorker] = None
        self.setup_ui()

    def setup_ui(self):
        self.setWindowTitle("TikTok Comment Receiver")
        self.resize(400, 600)
        self.setStyleSheet("""
            QMainWindow { background-color: #1e1e1e; color: #ffffff; }
            QLabel { color: #ffffff; font-size: 14px; font-weight: bold; margin: 10px 0; }
            QLineEdit { padding: 8px; border-radius: 5px; background-color: #2d2d2d; color: #fff; border: 1px solid #3d3d3d; }
            QPushButton { padding: 8px; background-color: #0078d4; color: white; border-radius: 5px; border: none; font-weight: bold; }
            QPushButton:hover { background-color: #1084e0; }
            QPushButton:disabled { background-color: #333333; color: #888888; }
            QTextEdit { background-color: #1e1e1e; color: #cccccc; border: 1px solid #333333; font-family: 'Segoe UI', sans-serif; font-size: 10pt; padding: 5px; }
        """)

        # Central Widget
        container = QWidget()
        self.setCentralWidget(container)
        layout = QVBoxLayout(container)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)

        # Header
        title_label = QLabel("TikTok Live Monitor")
        layout.addWidget(title_label)

        # Input Area
        input_layout = QHBoxLayout()
        self.input_username = QLineEdit()
        self.input_username.setPlaceholderText("@username")
        self.input_username.setText("@isaackogz")
        
        self.btn_connect = QPushButton("Sambungkan")
        self.btn_connect.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_connect.clicked.connect(self.toggle_connection)

        input_layout.addWidget(self.input_username)
        input_layout.addWidget(self.btn_connect)
        layout.addLayout(input_layout)

        # Log Area
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        layout.addWidget(self.log_display)

    def toggle_connection(self):
        if self.worker is not None and self.worker.isRunning():
            self.stop_worker()
        else:
            self.start_worker()

    def start_worker(self):
        username = self.input_username.text().strip()
        if not username:
            self.append_log("Error: Username wajib diisi!")
            return

        self.input_username.setEnabled(False)
        self.btn_connect.setText("Putuskan")
        self.btn_connect.setStyleSheet("background-color: #d93025;")  # Merah saat disconnect
        self.log_display.clear()
        
        self.worker = TikTokWorker(username)
        self.worker.sig_connected.connect(lambda u, r: self.append_log(f"✅ Connected to {u}"))
        self.worker.sig_comment.connect(self.append_comment)
        self.worker.sig_log.connect(self.append_log)
        self.worker.sig_error.connect(self.on_worker_error)
        self.worker.sig_disconnected.connect(self.on_disconnected)
        self.worker.start()

    def stop_worker(self):
        self.btn_connect.setText("Memutuskan...")
        self.btn_connect.setEnabled(False)
        if self.worker:
            self.worker.stop()

    def on_disconnected(self):
        self.worker = None
        self.input_username.setEnabled(True)
        self.btn_connect.setText("Sambungkan")
        self.btn_connect.setEnabled(True)
        self.btn_connect.setStyleSheet("background-color: #0078d4;") # Biru saat connect
        self.append_log("--- Disconnected ---")

    def on_worker_error(self, msg):
        self.append_log(f"❌ Error: {msg}")

    def append_comment(self, user, comment):
        # HTML Formatting untuk warna
        html = f'<div style="margin-bottom: 2px;"><span style="color: #4cc2ff; font-weight: bold;">{user}:</span> <span style="color: #dddddd;">{comment}</span></div>'
        self.log_display.append(html)
        self.scroll_to_bottom()

    def append_log(self, text):
        self.log_display.append(f'<div style="color: #888888;">{text}</div>')
        self.scroll_to_bottom()

    def scroll_to_bottom(self):
        self.log_display.moveCursor(QTextCursor.MoveOperation.End)

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

if __name__ == '__main__':
    # Setup High DPI
    if hasattr(Qt.HighDpiScaleFactorRoundingPolicy, 'PassThrough'):
        QApplication.setHighDpiScaleFactorRoundingPolicy(Qt.HighDpiScaleFactorRoundingPolicy.PassThrough)

    # Init App
    app = QApplication(sys.argv)
    
    # Create Window
    window = MainWindow()
    window.show()

    # Run Loop
    sys.exit(app.exec())