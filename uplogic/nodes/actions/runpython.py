from uplogic.nodes import ULActionNode
from uplogic.nodes import ULOutSocket
from uplogic.utils.constants import STATUS_INVALID
from uplogic.utils import is_waiting
from uplogic.utils import not_met

import inspect
import asyncio
import threading
import bge

def schedule(coroutine):
    def runner():
        def check_game_running(loop,task):
            if not hasattr(bge.logic,'getCurrentScene'):
                print("Coroutine thread closed because the game ended.")
                task.cancel()
            elif not task.done():
                loop.call_later(1,check_game_running,loop,task)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        task = loop.create_task(coroutine)
        loop.call_later(1,check_game_running,loop,task)
        try:
            loop.run_until_complete(task)
        finally:
            loop.close()
            #print("Coroutine thread closed")
    thread = threading.Thread(target=runner)
    thread.start()
    return thread

class ULRunPython(ULActionNode):
    def __init__(self):
        ULActionNode.__init__(self)
        self.condition = None
        self.module_name = None
        self.module_func = None
        self.arg = None
        self.val = None
        self.OUT = ULOutSocket(self, self.get_done)
        self.VAL = ULOutSocket(self, self.get_val)
        self._old_mod_name = None
        self._old_mod_fun = None
        self._module = None
        self._modfun = None
        self._evaluating = False

    def get_done(self):
        return self.done

    def get_val(self):
        return self.val

    def evaluate(self):
        condition = self.get_input(self.condition)
        if not_met(condition):
            return
        mname = self.get_input(self.module_name)
        mfun = self.get_input(self.module_func)
        if is_waiting(mname, mfun):
            return
        args = None if self.arg is STATUS_INVALID else [
            self.get_input(arg)
            for arg in self.arg
        ]
        if mname and (self._old_mod_name != mname):
            exec("import {}".format(mname))
            self._old_mod_name = mname
            self._module = eval(mname)
        if self._old_mod_fun != mfun:
            self._modfun = getattr(self._module, mfun)
            self._old_mod_fun = mfun

        if self._evaluating:
            return
        self.done = False
        self._evaluating = True

        val = self._modfun(*args) if args else self._modfun()

        if inspect.iscoroutine(val):
            async def coroutine():
                try:
                    self.val = await val
                    self.done = True
                    self._set_ready()
                    self._evaluating = False
                except:
                    pass
            schedule(coroutine())
        else:
            self.val = val
            self.done = True
            self._set_ready()
            self._evaluating = False