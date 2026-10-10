"""Trusted Python writer bounds plus kernel file/CPU caps, not a native sandbox."""
from dataclasses import asdict, dataclass
import ctypes
import os
import platform
import resource
import signal
import sys


class ResourceBoundExceeded(BaseException):
    pass


@dataclass(frozen=True)
class Limits:
    wall_seconds: float = 600.
    cpu_seconds: int = 600
    file_bytes: int = 2 * 1024 * 1024
    write_reservations: int = 120
    directory_reservations: int = 16
    resource_policy: str = 'default'

    def __post_init__(self):
        ceilings = {'default': (2 * 1024 * 1024, 120),
                    'research_161': (8 * 1024 * 1024, 360)}
        if type(self.resource_policy) is not str or self.resource_policy not in ceilings:
            raise ValueError('explicit admitted resource policy required')
        file_ceiling, write_ceiling = ceilings[self.resource_policy]
        if not (type(self.wall_seconds) in (float, int) and 0 < self.wall_seconds <= 600
                and type(self.cpu_seconds) is int and 1 <= self.cpu_seconds <= 600
                and type(self.file_bytes) is int and 1 <= self.file_bytes <= file_ceiling
                and type(self.write_reservations) is int and 1 <= self.write_reservations <= write_ceiling
                and type(self.directory_reservations) is int and 1 <= self.directory_reservations <= 16):
            raise ValueError('explicit bounded worker limits required')

    def to_dict(self):
        return asdict(self)

    @property
    def logical_payload_bound(self):
        return self.file_bytes * self.write_reservations


class WriteBudget:
    """Monotonic conservative write/link reservation count, never refunded.

    Python-audited writable opens and links consume tokens before dispatch.
    Reopening the same file also consumes a token. Native unaudited writes are
    outside this trusted-source contract; no adversarial sandbox claim is made.
    """
    def __init__(self, limits):
        self.limits = limits
        self.writes = 1  # Parent-created, kernel-bounded stderr occupies one token.
        self.directories = 0

    def __call__(self, event, args):
        if event in ('subprocess.Popen', 'os.fork', 'os.forkpty', 'os.posix_spawn',
                     'os.exec', 'os.system', 'pty.spawn'):
            raise ResourceBoundExceeded('worker child processes forbidden')
        if event == 'open':
            _, mode, flags = args
            writing = bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))
            writing |= bool(mode and any(c in mode for c in 'wax+'))
            if writing:
                if self.writes >= self.limits.write_reservations:
                    raise ResourceBoundExceeded('worker write reservation limit reached')
                self.writes += 1
        elif event == 'os.link':
            if self.writes >= self.limits.write_reservations:
                raise ResourceBoundExceeded('worker link reservation limit reached')
            self.writes += 1
        elif event == 'os.mkdir':
            if self.directories >= self.limits.directory_reservations:
                raise ResourceBoundExceeded('worker directory reservation limit reached')
            self.directories += 1
        elif event in ('os.symlink', 'os.rename', 'os.truncate'):
            raise ResourceBoundExceeded('unadmitted worker filesystem mutation')

    def snapshot(self):
        return {'write_reservations_used': self.writes,
                'directory_reservations_used': self.directories,
                'logical_payload_bound_bytes': self.limits.logical_payload_bound,
                'boundary': 'trusted_source_python_audited_writes_not_hostile_native_sandbox'}


def install(limits, expected_parent_pid):
    """Call before any workload imports; parent-death race fails closed."""
    if sys.platform != 'linux':
        raise RuntimeError('Linux parent-death protection required')
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), 'parent-death signal setup failed')
    if os.getppid() != expected_parent_pid:
        os.kill(os.getpid(), signal.SIGKILL)
    resource.setrlimit(resource.RLIMIT_CPU, (limits.cpu_seconds, limits.cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (limits.file_bytes, limits.file_bytes))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    # Frozen provenance lazily runs the platform's uname helper. Resolve this
    # bounded standard-library metadata bootstrap under parent-death/CPU/file
    # protection, before forbidding child processes for all arm work.
    platform.platform()
    budget = WriteBudget(limits)
    sys.addaudithook(budget)
    return budget
