"""Track and stop only subprocesses owned by this evaluation process."""

from __future__ import annotations

import asyncio
from pathlib import Path

import psutil


class OwnedProcessTree:
    def __init__(self, process: psutil.Process):
        if not process.is_running():
            raise RuntimeError("Subprocess exited before ownership could be established; inspect its logs")
        if process.pid not in {p.pid for p in psutil.Process().children(recursive=True)}:
            raise RuntimeError("Refusing ownership of a process outside this runner")
        self.root = process
        self.members: dict[int, psutil.Process] = {}
        self.capture()

    @classmethod
    def discover(cls, executable: Path, required_argument: str, *, exclude=()):
        matches = []
        for process in psutil.Process().children(recursive=True):
            try:
                if (Path(process.exe()).resolve() == executable.resolve()
                        and required_argument in process.cmdline()
                        and (process.pid, process.create_time()) not in exclude):
                    matches.append(process)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        if len(matches) != 1:
            raise RuntimeError(f"Expected one owned {executable.name} process; found {len(matches)}")
        return cls(matches[0])

    def capture(self):
        # psutil.Process retains creation time and guards against PID reuse.
        if self.root.is_running():
            self.members[self.root.pid] = self.root
            try:
                for child in self.root.children(recursive=True):
                    # Windows retains a dead parent's PID. If that PID is reused
                    # by this root, psutil can list older, unrelated descendants.
                    # A child cannot have been created before any of its parents.
                    current = child
                    valid = True
                    while current.pid != self.root.pid:
                        parent = current.parent()
                        if parent is None or parent.create_time() > current.create_time():
                            valid = False
                            break
                        current = parent
                    if valid:
                        self.members[child.pid] = child
            except psutil.NoSuchProcess:
                pass

    async def finish(self) -> dict:
        """Allow graceful exit, then stop only captured surviving descendants."""
        self.capture()
        _, alive = await asyncio.to_thread(psutil.wait_procs,
                                          [p for p in self.members.values() if p.is_running()], timeout=5)
        # wait() on Windows can observe a reused PID. is_running() compares
        # the cached creation time and excludes a different process identity.
        alive = [p for p in alive if p.is_running()]
        forced = [p.pid for p in alive]
        for process in alive:
            try:
                process.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = await asyncio.to_thread(psutil.wait_procs, alive, timeout=3)
        alive = [p for p in alive if p.is_running()]
        for process in alive:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        _, alive = await asyncio.to_thread(psutil.wait_procs, alive, timeout=3)
        alive = [p for p in alive if p.is_running()]
        if alive:
            raise RuntimeError(f"Owned processes did not exit: {[p.pid for p in alive]}")
        return {"pids": sorted(self.members), "forced_pids": forced, "all_exited": True}
