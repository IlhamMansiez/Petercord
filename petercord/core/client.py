# petercord

__all__ = ['Petercord']

import asyncio
import functools
import importlib
import inspect
import os
import signal
import threading
import time
from types import ModuleType
from typing import List, Awaitable, Any, Optional, Union

from pyrogram import idle, types
from pyrogram.methods import Methods as RawMethods

from petercord import logging, Config, logbot, get_version
from petercord.plugins import get_all_plugins
from petercord.utils import time_formatter
from petercord.utils.exceptions import PetercordBotNotFound
from .database import get_collection
from .ext import RawClient
from .methods import Methods

_LOG = logging.getLogger(__name__)
_LOG_STR = "<<<!  #####  %s  #####  !>>>"

_IMPORTED: List[ModuleType] = []
_INIT_TASKS: List[asyncio.Task] = []
_START_TIME = time.time()
_SEND_SIGNAL = False

_PETERCORD_STATUS = get_collection("PETERCORD_STATUS")


async def _set_running(is_running: bool) -> None:
    await _PETERCORD_STATUS.update_one(
        {'_id': 'PETERCORD_STATUS'},
        {"$set": {'is_running': is_running}},
        upsert=True
    )


async def _is_running() -> bool:
    if Config.ASSERT_SINGLE_INSTANCE:
        data = await _PETERCORD_STATUS.find_one({'_id': 'PETERCORD_STATUS'})
        if data:
            return bool(data['is_running'])
    return False


async def _complete_init_tasks() -> None:
    if not _INIT_TASKS:
        return
    await asyncio.gather(*_INIT_TASKS)
    _INIT_TASKS.clear()


class _AbstractPetercord(Methods, RawClient):
    def __init__(self, **kwargs) -> None:
        self._me: Optional[types.User] = None
        super().__init__(**kwargs)

    @property
    def id(self) -> int:
        """ returns client id """
        if self.is_bot:
            return RawClient.BOT_ID
        return RawClient.USER_ID

    @property
    def is_bot(self) -> bool:
        """ returns client is bot or not """
        if self._bot is not None:
            return hasattr(self, 'ubot')
        return bool(Config.BOT_TOKEN)

    @property
    def uptime(self) -> str:
        """ returns userge uptime """
        return time_formatter(time.time() - _START_TIME)

    async def finalize_load(self) -> None:
        """ finalize the plugins load """
        await asyncio.gather(_complete_init_tasks(), self.manager.init())

    async def load_plugin(self, name: str, reload_plugin: bool = False) -> None:
        """ Load plugin to Petercord-X """
        _LOG.debug(_LOG_STR, f"Importing {name}")
        _IMPORTED.append(
            importlib.import_module(f"petercord.plugins.{name}"))
        if reload_plugin:
            _IMPORTED[-1] = importlib.reload(_IMPORTED[-1])
        plg = _IMPORTED[-1]
        self.manager.update_plugin(plg.__name__, plg.__doc__)
        if hasattr(plg, '_init'):
            # pylint: disable=protected-access
            if asyncio.iscoroutinefunction(plg._init):
                _INIT_TASKS.append(self.loop.create_task(plg._init()))
        _LOG.debug(_LOG_STR, f"Imported {_IMPORTED[-1].__name__} Plugin Successfully")

    async def _load_plugins(self) -> None:
        _IMPORTED.clear()
        _INIT_TASKS.clear()
        logbot.edit_last_msg("Importing All Plugins", _LOG.info, _LOG_STR)
        for name in get_all_plugins():
            try:
                await self.load_plugin(name)
            except Exception as i_e:
                _LOG.error(_LOG_STR, f"[{name}] - {i_e}")
        await self.finalize_load()
        _LOG.info(_LOG_STR, f"Imported ({len(_IMPORTED)}) Plugins => "
                  + str([i.__name__ for i in _IMPORTED]))

    async def reload_plugins(self) -> int:
        """ Reload all Plugins """
        self.manager.clear_plugins()
        reloaded: List[str] = []
        _LOG.info(_LOG_STR, "Reloading All Plugins")
        for imported in _IMPORTED:
            try:
                reloaded_ = importlib.reload(imported)
            except Exception as i_e:
                _LOG.error(_LOG_STR, i_e)
            else:
                reloaded.append(reloaded_.__name__)
        _LOG.info(_LOG_STR, f"Reloaded {len(reloaded)} Plugins => {reloaded}")
        await self.finalize_load()
        return len(reloaded)

    async def get_me(self, cached: bool = True) -> types.User:
        if not cached or self._me is None:
            self._me = await super().get_me()
        return self._me

    async def start(self):
        await super().start()
        self._me = await self.get_me()
        if self.is_bot:
            RawClient.BOT_ID = self._me.id
        else:
            RawClient.USER_ID = self._me.id

    def __eq__(self, o: object) -> bool:
        return isinstance(o, _AbstractPetercord) and self.id == o.id

    def __hash__(self) -> int:  # pylint: disable=W0235
        return super().__hash__()

ON = f"""
👥 **Petercord-X Aktif**
•••••••••••
💻 **Version -** `{get_version()}`

❗Sebaiknya Anda jangan keluar grup ini agar bot tidak mati
 ....Terimakasih....🇮🇩
❗You should not leave this group so that the bot does not die
 ....Thank You....🇺🇸
•••••••••••
"""

class PetercordBot(_AbstractPetercord):
    """ UsergeBot, the bot """
    def __init__(self, **kwargs) -> None:
        _LOG.info(_LOG_STR, "Setting Petercord-X Configs")
        super().__init__(session_name=":memory:", **kwargs)

    @property
    def ubot(self) -> 'Petercord':
        """ returns userbot """
        return self._bot


class Petercord(_AbstractPetercord):
    """ Userge, the userbot """

    has_bot = bool(Config.BOT_TOKEN)

    def __init__(self, **kwargs) -> None:
        _LOG.info(_LOG_STR, "Setting Petercord-X Configs")
        kwargs = {
            'api_id': Config.API_ID,
            'api_hash': Config.API_HASH,
            'workers': Config.WORKERS
        }
        if Config.BOT_TOKEN:
            kwargs['bot_token'] = Config.BOT_TOKEN
        if Config.HU_STRING_SESSION and Config.BOT_TOKEN:
            RawClient.DUAL_MODE = True
            kwargs['bot'] = PetercordBot(bot=self, **kwargs)
        kwargs['session_name'] = Config.HU_STRING_SESSION or ":memory:"
        super().__init__(**kwargs)

    @property
    def dual_mode(self) -> bool:
        return RawClient.DUAL_MODE

    @property
    def bot(self) -> Union['PetercordBot', 'Petercord']:
        """ returns usergebot """
        if self._bot is None:
            if Config.BOT_TOKEN:
                return self
            raise PetercordBotNotFound("Need BOT_TOKEN ENV!")
        return self._bot

    async def start(self) -> None:
        """ start client and bot """
        counter = 0
        timeout = 30  # 30 sec
        max_ = 1800  # 30 min

        while await _is_running():
            _LOG.info(_LOG_STR, "Waiting for the Termination of "
                                f"previous Petercord-X instance ... [{timeout} sec]")
            time.sleep(timeout)

            counter += timeout
            if counter >= max_:
                _LOG.info(_LOG_STR, f"Max timeout reached ! [{max_} sec]")
                break

        _LOG.info(_LOG_STR, "Starting Petercord-X")
        await _set_running(True)
        await super().start()
        if self._bot is not None:
            _LOG.info(_LOG_STR, "Starting Asisten")
            await self._bot.start()
        await self._load_plugins()

    async def stop(self) -> None:  # pylint: disable=arguments-differ
        """ stop client and bot """
        if self._bot is not None:
            _LOG.info(_LOG_STR, "Stopping Asisten")
            await self._bot.stop()
        _LOG.info(_LOG_STR, "Stopping Petercord-X")
        await super().stop()
        await _set_running(False)

    def begin(self, coro: Optional[Awaitable[Any]] = None) -> None:
        """ start Petercord-X """
        lock = asyncio.Lock()
        loop_is_stopped = asyncio.Event()
        running_tasks: List[asyncio.Task] = []

        async def _waiter() -> None:
            try:
                await asyncio.wait_for(loop_is_stopped.wait(), 30)
            except asyncio.exceptions.TimeoutError:
                pass

        async def _finalize() -> None:
            async with lock:
                for t in running_tasks:
                    t.cancel()
                if self.is_initialized:
                    await self.stop()
            # pylint: disable=expression-not-assigned
            [t.cancel() for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            await self.loop.shutdown_asyncgens()
            self.loop.stop()
            _LOG.info(_LOG_STR, "Loop Stopped !")
            loop_is_stopped.set()

        async def _shutdown(_sig: signal.Signals) -> None:
            global _SEND_SIGNAL  # pylint: disable=global-statement
            _LOG.info(_LOG_STR, f"Received Stop Signal [{_sig.name}], Exiting Petercord-X ...")
            await _finalize()
            if _sig == _sig.SIGUSR1:
                _SEND_SIGNAL = True

        for sig in (signal.SIGHUP, signal.SIGTERM, signal.SIGINT, signal.SIGUSR1):
            self.loop.add_signal_handler(
                sig, lambda _sig=sig: self.loop.create_task(_shutdown(_sig)))

        try:
            self.loop.run_until_complete(self.start())
        except RuntimeError:
            return

        for task in self._tasks:
            running_tasks.append(self.loop.create_task(task()))
         logbot.edit_last_msg(f"👥 **Petercord-X Aktif**\n•••••••••••\n💻 **Version -** `{get_version()}`\n\n❗Sebaiknya Anda jangan keluar grup ini agar bot tidak mati\n....Terimakasih....🇮🇩\n❗You should not leave this group so that the bot does not die\n....Thank You....🇺🇸\n•••••••••••")
        logbot.edit_last_msg("Petercord-X Started Successfully !")
        logbot.end()
        mode = "[DUAL]" if RawClient.DUAL_MODE else "[BOT]" if Config.BOT_TOKEN else "[USER]"

        try:
            if coro:
                _LOG.info(_LOG_STR, f"Running Coroutine - {mode}")
                self.loop.run_until_complete(coro)
            else:
                _LOG.info(_LOG_STR, f"Idling Petercord-X - {mode}")
                idle()
            self.loop.run_until_complete(_finalize())
        except (asyncio.exceptions.CancelledError, RuntimeError):
            pass
        finally:
            try:
                self.loop.run_until_complete(_waiter())
            except RuntimeError:
                pass
            if _SEND_SIGNAL:
                os.kill(os.getpid(), signal.SIGUSR1)


def _un_wrapper(obj, name, function):
    loop = asyncio.get_event_loop()

    @functools.wraps(function)
    def _wrapper(*args, **kwargs):
        coroutine = function(*args, **kwargs)
        if (threading.current_thread() is not threading.main_thread()
                and inspect.iscoroutine(coroutine)):
            async def _():
                return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coroutine, loop))
            return _()
        return coroutine

    setattr(obj, name, _wrapper)


def _un_wrap(source):
    for name in dir(source):
        if name.startswith("_"):
            continue
        wrapped = getattr(getattr(source, name), '__wrapped__', None)
        if wrapped and (inspect.iscoroutinefunction(wrapped)
                        or inspect.isasyncgenfunction(wrapped)):
            _un_wrapper(source, name, wrapped)


_un_wrap(RawMethods)
for class_name in dir(types):
    cls = getattr(types, class_name)
    if inspect.isclass(cls):
        _un_wrap(cls)
